import numpy as np
import pytest
from anndata import AnnData

from dance.data import Data

X = np.array([[0, 1], [1, 2], [2, 3]])
Y = np.array([[0], [1], [2]])


def test_data_basic_properties(subtests):
    adata = AnnData(X=X)

    with subtests.test("No training splits"):
        data = Data(adata)
        assert data.num_cells == 3
        assert data.num_features == 2
        assert data.cells == ["0", "1", "2"]
        assert data.train_idx is data.val_idx is data.test_idx is None

    with subtests.test("All training"):
        data = Data(adata, train_size="all")
        assert data.train_idx == [0, 1, 2]
        assert data.val_idx is None
        assert data.test_idx is None

    with subtests.test("Training and testing splits"):
        data = Data(adata, train_size=2)
        assert data.train_idx == [0, 1]
        assert data.val_idx is None
        assert data.test_idx == [2]

        data = Data(adata, train_size=-1, test_size=1)
        assert data.train_idx == [0, 1]
        assert data.val_idx is None
        assert data.test_idx == [2]

    with subtests.test("Training validation and testing splits"):
        data = Data(adata, train_size=1, val_size=1)
        assert data.train_idx == [0]
        assert data.val_idx == [1]
        assert data.test_idx == [2]

    with subtests.test("Error sizes"):
        with pytest.raises(TypeError):
            Data(adata, train_size="1")
        with pytest.raises(ValueError):  # cannot have two -1
            Data(adata, train_size=-1)
        with pytest.raises(ValueError):  # train size exceeds data size
            Data(adata, train_size=5)
        with pytest.raises(ValueError):  # sum of sizes exceeds data size
            Data(adata, train_size=2, test_size=2)


def test_get_data(subtests):
    adata = AnnData(X=X)
    adata.obsm["feature1"] = X + 10
    adata.obsm["feature2"] = X + 20
    adata.obsm["obsm_feature"] = X
    adata.obsp["obsp_feature"] = X @ X.T
    adata.varm["varm_feature"] = X.T
    adata.varp["varp_feature"] = X.T @ X
    adata.obsm["label"] = Y

    with subtests.test("Single feature"):
        data = Data(adata, train_size=2)
        data.set_config(label_channel="label")

        x_train, y_train = data.get_train_data()
        assert x_train.tolist() == [[0, 1], [1, 2]]
        assert y_train.tolist() == [[0], [1]]

        x_test, y_test = data.get_test_data()
        assert x_test.tolist() == [[2, 3]]
        assert y_test.tolist() == [[2]]

        # Validation set not set
        pytest.raises(KeyError, data.get_val_data)

    with subtests.test("Multi feature"):
        data = Data(adata, train_size=2)
        data.set_config(feature_channel=[None, "feature1", "feature2"], label_channel="label")

        (x1_train, x2_train, x3_train), y_train = data.get_train_data()
        assert x2_train.tolist() == [[10, 11], [11, 12]]
        assert x3_train.tolist() == [[20, 21], [21, 22]]
        assert y_train.tolist() == [[0], [1]]

    with subtests.test("Multi type feature"):
        data = Data(adata, train_size=2)
        data.set_config(feature_channel=["obsm_feature", "obsp_feature", "varm_feature", "varp_feature"],
                        channel_type=["obsm", "obsp", "varm", "varp"], label_channel="label")

        (x_obsm, x_obsp, x_varm, x_varp), y = data.get_train_data()
        assert x_obsm.tolist() == [[0, 1], [1, 2]]
        assert x_obsp.tolist() == [[1, 2], [2, 5]]
        assert x_varm.tolist() == [[0, 1, 2], [1, 2, 3]]
        assert x_varp.tolist() == [[5, 8], [8, 14]]
        assert y.tolist() == [[0], [1]]
