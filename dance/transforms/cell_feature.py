import numpy as np
import pandas as pd
from sklearn.decomposition import PCA, TruncatedSVD

from dance.registry import register_preprocessor
from dance.transforms.base import BaseTransform
from dance.typing import Optional, Union
from dance.utils.matrix import normalize
from dance.utils.status import deprecated


@register_preprocessor("feature", "cell")
class WeightedFeaturePCA(BaseTransform):
    """Compute the weighted gene PCA as cell features.

    Given a gene expression matrix of dimension (cell x gene), the gene PCA is first compured. Then, the representation
    of each cell is computed by taking the weighted sum of the gene PCAs based on that cell's gene expression values.

    Parameters
    ----------
    n_components
        Number of PCs to use.
    split_name
        Which split to use to compute the gene PCA. If not set, use all data.
    feat_norm_mode
        Feature normalization mode, see :func:`dance.utils.matrix.normalize`. If set to `None`, then do not perform
        feature normalization before reduction.

    """

    _DISPLAY_ATTRS = ("n_components", "split_name", "feat_norm_mode", "feat_norm_axis")

    def __init__(self, n_components: Union[float, int] = 0.9, split_name: Optional[str] = None,
                 feat_norm_mode: Optional[str] = None, feat_norm_axis: int = 0, **kwargs):
        super().__init__(**kwargs)

        self.n_components = n_components
        self.split_name = split_name
        self.feat_norm_mode = feat_norm_mode
        self.feat_norm_axis = feat_norm_axis

    def __call__(self, data):
        feat = data.get_x(self.split_name)  # cell x genes
        if self.feat_norm_mode is not None:
            self.logger.info(f"Normalizing feature before PCA decomposition with mode={self.feat_norm_mode} "
                             f"and axis={self.feat_norm_axis}")
            feat = normalize(feat, mode=self.feat_norm_mode, axis=self.feat_norm_axis)
        gene_pca = PCA(n_components=self.n_components)

        gene_feat = gene_pca.fit_transform(feat.T)  # decompose into gene features
        self.logger.info(f"Decomposing {self.split_name} features {feat.shape} (k={gene_pca.n_components_})")
        self.logger.info(f"Total explained variance: {gene_pca.explained_variance_ratio_.sum():.2%}")

        x = data.get_x()
        cell_feat = normalize(x, mode="normalize", axis=1) @ gene_feat
        data.data.obsm[self.out] = cell_feat.astype(np.float32)
        data.data.varm[self.out] = gene_feat.astype(np.float32)

        return data


@register_preprocessor("feature", "cell")
class WeightedFeatureSVD(BaseTransform):
    """Compute the weighted gene SVD as cell features.

    Given a gene expression matrix of dimension (cell x gene), the gene SVD is first compured. Then, the representation
    of each cell is computed by taking the weighted sum of the gene PCAs based on that cell's gene expression values.

    Parameters
    ----------
    n_components
        Desired dimensionality of output data.
    split_name
        Which split to use to compute the gene SVD. If not set, use all data.
    feat_norm_mode
        Feature normalization mode, see :func:`dance.utils.matrix.normalize`. If set to `None`, then do not perform
        feature normalization before reduction.

    """

    _DISPLAY_ATTRS = ("n_components", "split_name", "feat_norm_mode", "feat_norm_axis")

    def __init__(self, n_components: Union[float, int] = 0.9, split_name: Optional[str] = None,
                 feat_norm_mode: Optional[str] = None, feat_norm_axis: int = 0, **kwargs):
        super().__init__(**kwargs)

        self.n_components = n_components
        self.split_name = split_name
        self.feat_norm_mode = feat_norm_mode
        self.feat_norm_axis = feat_norm_axis

    def __call__(self, data):
        feat = data.get_x(self.split_name)  # cell x genes
        if isinstance(self.n_components, float):
            n_components = min(feat.shape) - 1
            svd = TruncatedSVD(n_components=n_components)
            svd.fit_transform(feat)
            explained_variance = svd.explained_variance_ratio_.cumsum()
            self.n_components = (explained_variance < self.n_components).sum() + 1
        if self.feat_norm_mode is not None:
            self.logger.info(f"Normalizing feature before PCA decomposition with mode={self.feat_norm_mode} "
                             f"and axis={self.feat_norm_axis}")
            feat = normalize(feat, mode=self.feat_norm_mode, axis=self.feat_norm_axis)
        gene_svd = TruncatedSVD(n_components=self.n_components)

        gene_feat = gene_svd.fit_transform(feat.T)  # decompose into gene features
        self.logger.info(f"Decomposing {self.split_name} features {feat.shape} (k={self.n_components})")
        self.logger.info(f"Total explained variance: {gene_svd.explained_variance_ratio_.sum():.2%}")

        x = data.get_x()
        cell_feat = normalize(x, mode="normalize", axis=1) @ gene_feat
        data.data.obsm[self.out] = cell_feat.astype(np.float32)
        data.data.varm[self.out] = gene_feat.astype(np.float32)

        return data


@register_preprocessor("feature", "cell")
class CellPCA(BaseTransform):
    """Reduce cell feature matrix with PCA.

    Parameters
    ----------
    n_components
        Number of PCA components to use.

    """

    _DISPLAY_ATTRS = ("n_components", )

    def __init__(self, n_components: Union[float, int] = 0.9, *, channel: Optional[str] = None,
                 mod: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)

        self.n_components = n_components
        self.channel = channel
        self.mod = mod

    def __call__(self, data):
        feat = data.get_feature(return_type="numpy", channel=self.channel, mod=self.mod)
        pca = PCA(n_components=self.n_components)
        cell_feat = pca.fit_transform(feat)
        self.logger.info(f"Generating cell PCA features {feat.shape} (k={pca.n_components_})")
        evr = pca.explained_variance_ratio_
        self.logger.info(f"Top 10 explained variances: {evr[:10]}")
        self.logger.info(f"Total explained variance: {evr.sum():.2%}")

        data.data.obsm[self.out] = cell_feat

        return data


@register_preprocessor("feature", "cell")
class CellSVD(BaseTransform):
    """Reduce cell feature matrix with SVD.

    Parameters
    ----------
    n_components
        Number of SVD components to take.

    """

    _DISPLAY_ATTRS = ("n_components", )

    def __init__(self, n_components: Union[float, int] = 0.9, *, channel: Optional[str] = None,
                 mod: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)

        self.n_components = n_components
        self.channel = channel
        self.mod = mod

    def __call__(self, data):
        feat = data.get_feature(return_type="numpy", channel=self.channel, mod=self.mod)
        if isinstance(self.n_components, float):
            n_components = min(feat.shape) - 1
            svd = TruncatedSVD(n_components=n_components)
            svd.fit_transform(feat)
            explained_variance = svd.explained_variance_ratio_.cumsum()
            self.n_components = (explained_variance < self.n_components).sum() + 1
        svd = TruncatedSVD(n_components=self.n_components)

        cell_feat = svd.fit_transform(feat)
        self.logger.info(f"Generating cell SVD features {feat.shape} (k={self.n_components})")

        evr = svd.explained_variance_ratio_
        self.logger.info(f"Top 10 explained variances: {evr[:10]}")
        self.logger.info(f"Total explained variance: {evr.sum():.2%}")

        data.data.obsm[self.out] = cell_feat

        return data


@register_preprocessor("feature", "cell")
@deprecated(msg="will be replaced by builtin bypass mechanism in pipeline")
class FeatureCellPlaceHolder(BaseTransform):
    """Used as a placeholder to skip the process.

    Parameters
    ----------
    n_components
        it will not be used

    """

    def __init__(self, n_components: int = 400, *, channel: Optional[str] = None, mod: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.channel = channel
        self.mod = mod
        self.logger.info(
            "n_components in FeatureCellPlaceHolder is used to make the parameters consistent and will not have any actual effect."
        )

    def __call__(self, data):
        """If we follow WeightedFeaturePCA, then gene_feat should be the transpose of
        feat, and cell_feat is the product of feat and gene_feat, but considering that
        cell_feat is more commonly used, I did not do this."""
        feat = data.get_feature(return_type="numpy", channel=self.channel, mod=self.mod)
        cell_feat = feat
        gene_feat = feat.T @ feat
        data.data.obsm[self.out] = cell_feat
        data.data.varm[
            self.
            out] = gene_feat  #The vstack of gene_feat and cell_feat is required in the process of building CellFeatureGraph.


@register_preprocessor("feature", "cell")
class BatchFeature(BaseTransform):
    """Assign statistical batch features for each cell."""

    def __init__(self, *, channel: Optional[str] = None, mod: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.channel = channel
        self.mod = mod

    def __call__(self, data):
        # TODO: use get_feature; move mod1 to mod; replace for loop with np
        cells = []
        columns = [
            "cell_mean",
            "cell_std",
            "nonzero_25%",
            "nonzero_50%",
            "nonzero_75%",
            "nonzero_max",
            "nonzero_count",
            "nonzero_mean",
            "nonzero_std",
            "batch",
        ]  # yapf: disable

        ad_input = data.data["mod1"]
        bcl = list(ad_input.obs["batch"])
        print(set(bcl))
        for i, cell in enumerate(ad_input.X):
            cell = cell.toarray()
            nz = cell[np.nonzero(cell)]
            if len(nz) == 0:
                raise ValueError("Error: one cell contains all zero features.")
            cells.append([
                cell.mean(),
                cell.std(),
                np.percentile(nz, 25),
                np.percentile(nz, 50),
                np.percentile(nz, 75),
                cell.max(),
                len(nz) / 1000,
                nz.mean(),
                nz.std(), bcl[i]
            ])

        cell_features = pd.DataFrame(cells, columns=columns)
        batch_source = cell_features.groupby("batch").mean().reset_index()
        batch_list = batch_source.batch.tolist()
        batch_source = batch_source.drop("batch", axis=1).to_numpy().tolist()
        b2i = dict(zip(batch_list, range(len(batch_list))))
        batch_features = []

        for b in ad_input.obs["batch"]:
            batch_features.append(batch_source[b2i[b]])

        batch_features = np.array(batch_features).astype(float)
        data.data["mod1"].obsm["batch_features"] = batch_features
        return data
