import abc
import logging
from typing import List
import unittest
import numpy as np

import batchglm.api as glm
from batchglm.models.base_glm import _Estimator_GLM, _Simulator_GLM

glm.setup_logging(verbosity="WARNING", stream="STDOUT")
logger = logging.getLogger(__name__)


class _Test_AccuracyAnalytic_GLM_Estim():

    def __init__(
            self,
            estimator: _Estimator_GLM,
            simulator: _Simulator_GLM
    ):
        self.estimator = estimator
        self.sim = simulator

    def estimate(self):
        self.estimator.initialize()
        self.estimator.train_sequence(training_strategy=[
            {
                "learning_rate": 1,
                "convergence_criteria": "all_converged_ll",
                "stopping_criteria": 1e-6,
                "use_batching": False,
                "optim_algo": "irls_gd_tr",
            },
        ])

    def eval_estimation_a(
            self,
            estimator_store,
            init
    ):
        threshold_dev = 1e-2
        threshold_std = 1e-1

        if init == "standard":
            mean_dev = np.mean(estimator_store.a[0, :] - self.sim.a[0, :])
            std_dev = np.std(estimator_store.a[0, :] - self.sim.a[0, :])
        elif init == "closed_form":
            mean_dev = np.mean(estimator_store.a - self.sim.a)
            std_dev = np.std(estimator_store.a - self.sim.a)
        else:
            assert False

        logging.getLogger("batchglm").info("mean_dev_a %f" % mean_dev)
        logging.getLogger("batchglm").info("std_dev_a %f" % std_dev)

        if np.abs(mean_dev) < threshold_dev and \
                std_dev < threshold_std:
            return True
        else:
            return False

    def eval_estimation_b(
            self,
            estimator_store,
            init
    ):
        threshold_dev = 1e-2
        threshold_std = 12-1

        if init == "standard":
            mean_dev = np.mean(estimator_store.b[0, :] - self.sim.b[0, :])
            std_dev = np.std(estimator_store.b[0, :] - self.sim.b[0, :])
        elif init == "closed_form":
            mean_dev = np.mean(estimator_store.b - self.sim.b)
            std_dev = np.std(estimator_store.b - self.sim.b)
        else:
            assert False

        logging.getLogger("batchglm").info("mean_dev_b %f" % mean_dev)
        logging.getLogger("batchglm").info("std_dev_b %f" % std_dev)

        if np.abs(mean_dev) < threshold_dev and \
                std_dev < threshold_std:
            return True
        else:
            return False


class Test_AccuracyAnalytic_GLM(unittest.TestCase, metaclass=abc.ABCMeta):
    """
    Test whether analytic solutions yield exact results.

    Accuracy is evaluted via deviation of simulated ground truth.
    The analytic solution is independent of the optimizer and batching
    and therefore only tested for one example each.

    - full data model
        - train a model only: test_a_analytic()
        - train b model only: test_b_analytic()

    The unit tests throw an assertion error if the required accurcy is
    not met.
    """
    _estims: List[_Test_AccuracyAnalytic_GLM_Estim]

    def setUp(self):
        self._estims = []

    def tearDown(self):
        for e in self._estims:
            e.estimator.close_session()

    @abc.abstractmethod
    def get_simulator(self):
        pass

    def simulate_complex(self):
        self.sim = self.get_simulator()
        self.sim.generate_sample_description(num_batches=1, num_conditions=2)
        self.sim.generate_params(
            rand_fn_ave=lambda shape: np.random.uniform(1e5, 2*1e5, shape),
            rand_fn_loc=lambda shape: np.random.uniform(1, 3, shape),
            rand_fn_scale=lambda shape: np.random.uniform(1, 3, shape)
        )
        self.sim.generate_data()

    def simulate_a_easy(self):
        self.sim = self.get_simulator()
        self.sim.generate_sample_description(num_batches=1, num_conditions=2)

        self.sim.generate_params(
            rand_fn_ave=lambda shape: np.random.uniform(1e5, 2 * 1e5, shape),
            rand_fn_loc=lambda shape: np.ones(shape),
            rand_fn_scale=lambda shape: np.random.uniform(5, 20, shape)
        )
        self.sim.generate_data()

    def simulate_b_easy(self):
        self.sim = self.get_simulator()
        self.sim.generate_sample_description(num_batches=1, num_conditions=2)

        def rand_fn_standard(shape):
            theta = np.ones(shape)
            theta[0, :] = np.random.uniform(5, 20, shape[1])
            return theta

        self.sim.generate_params(
            rand_fn_ave=lambda shape: np.random.uniform(1e5, 2 * 1e5, shape),
            rand_fn_loc=lambda shape: np.random.uniform(5, 20, shape),
            rand_fn_scale=lambda shape: rand_fn_standard(shape)
        )
        self.sim.generate_data()

    def simulate_a_b_easy(self):
        self.sim = self.get_simulator()
        self.sim.generate_sample_description(num_batches=1, num_conditions=2)

        def rand_fn_standard(shape):
            theta = np.ones(shape)
            theta[0, :] = np.random.uniform(5, 20, shape[1])
            return theta

        self.sim.generate_params(
            rand_fn_ave=lambda shape: np.random.uniform(1e5, 2 * 1e5, shape),
            rand_fn_loc=lambda shape: np.ones(shape),
            rand_fn_scale=lambda shape: rand_fn_standard(shape)
        )
        self.sim.generate_data()

    @abc.abstractmethod
    def get_estimator(self, train_scale, sparse, init_a, init_b):
        pass

    def _test_a_and_b(self, sparse, init_a, init_b):
        estimator = self.get_estimator(
            train_scale=False,
            sparse=sparse,
            init_a=init_a,
            init_b=init_b
        )
        estimator.estimate()
        estimator_store = estimator.estimator.finalize()
        self._estims.append(estimator)
        success = estimator.eval_estimation_a(
            estimator_store=estimator_store,
            init=init_a
        )
        assert success, "estimation for a_model was inaccurate"
        success = estimator.eval_estimation_b(
            estimator_store=estimator_store,
            init=init_b
        )
        assert success, "estimation for b_model was inaccurate"
        return True


if __name__ == '__main__':
    unittest.main()