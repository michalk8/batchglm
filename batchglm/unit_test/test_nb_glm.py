import os
import unittest
import tempfile

import numpy as np
from typing import List

from batchglm.api.models.nb_glm import Simulator, Estimator, InputData


# from utils.config import getConfig


def estimate(input_data: InputData, working_dir: str):
    print(input_data.X)

    estimator = Estimator(input_data, batch_size=500)
    estimator.initialize(
        working_dir=working_dir,
        save_checkpoint_steps=20,
        save_summaries_steps=20,
        # stop_at_step=1000,
        # stop_below_loss_change=1e-5,i

        export=["a", "b", "mu", "r", "loss"],
        export_steps=20
    )
    input_data.save(os.path.join(working_dir, "input_data.h5"))

    estimator.train_sequence()

    return estimator


class NB_GLM_Test(unittest.TestCase):
    sim: Simulator
    working_dir: tempfile.TemporaryDirectory

    _estims: List[Estimator]

    def setUp(self):
        self.sim = Simulator(num_observations=2000, num_features=100)
        self.sim.generate()
        self.working_dir = tempfile.TemporaryDirectory()

        self._estims = []
        print("working_dir: %s" % self.working_dir)

    def tearDown(self):
        for e in self._estims:
            e.close_session()

        self.working_dir.cleanup()

    def test_default_fit(self):
        sim = self.sim.__copy__()
        print(sim.input_data[2:4, [5, 6, 7]])

        wd = os.path.join(self.working_dir.name, "default_fit")
        os.makedirs(wd, exist_ok=True)

        estimator = estimate(sim.input_data, wd)
        self._estims.append(estimator)

        # test finalizing
        estimator = estimator.finalize()
        print(estimator.mu.values)
        print(estimator.gradient.values)
        print(estimator.hessian_diagonal.values)
        print(estimator.probs().values)
        print(estimator.log_probs().values)

        return estimator, sim

    def test_nonconfounded_fit(self):
        sim = Simulator(num_observations=2000, num_features=100)
        sim.generate_sample_description(num_confounders=0, num_batches=4)
        sim.generate()

        print(sim.input_data[2:4, [5, 6, 7]])

        wd = os.path.join(self.working_dir.name, "default_fit")
        os.makedirs(wd, exist_ok=True)

        estimator = estimate(sim.input_data, wd)
        print("Disabling training of 'r'; now should not train any more:")
        estimator.train(train_r=False)
        self._estims.append(estimator)

        # test finalizing
        estimator = estimator.finalize()
        print(estimator.mu.values)
        print(estimator.gradient.values)
        print(estimator.hessian_diagonal.values)
        print(estimator.probs().values)
        print(estimator.log_probs().values)

        return estimator, sim

    def test_anndata(self):
        adata = self.sim.data_to_anndata()
        idata = InputData.new(adata)

        wd = os.path.join(self.working_dir.name, "anndata")
        os.makedirs(wd, exist_ok=True)

        print(adata)
        estimator = estimate(idata, wd)
        self._estims.append(estimator)

        return estimator, adata

    def test_zero_variance(self):
        sim = self.sim.__copy__()
        sim.data.X[:, 0] = np.exp(sim.a)[0, 0]

        wd = os.path.join(self.working_dir.name, "zero_variance")
        os.makedirs(wd, exist_ok=True)

        estimator = estimate(sim.input_data, wd)
        self._estims.append(estimator)

        return estimator, sim

    def test_low_values(self):
        sim = self.sim.__copy__()
        sim.data.X[:, 0] = 0

        wd = os.path.join(self.working_dir.name, "low_values")
        os.makedirs(wd, exist_ok=True)

        estimator = estimate(sim.input_data, wd)
        self._estims.append(estimator)

        return estimator, sim

    def test_nonsense_data(self):
        sim = self.sim.__copy__()
        sim.data.X[:, :] = 0
        sim.data.X[0, 0] = 12

        wd = os.path.join(self.working_dir.name, "nonsense_data")
        os.makedirs(wd, exist_ok=True)

        estimator = estimate(sim.input_data, wd)
        self._estims.append(estimator)

        return estimator, sim


if __name__ == '__main__':
    unittest.main()