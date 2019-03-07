import logging

import tensorflow as tf

from .external import pkg_constants
from .external import HessiansGLM

logger = logging.getLogger(__name__)


class HessianGLMALL(HessiansGLM):
    """
    Compute the Hessian matrix for a GLM by gene using gradients from tensorflow.
    """

    def hessian_analytic(
            self,
            model
    ) -> tf.Tensor:
        """
        Compute the closed-form of the base_glm_all model hessian
        by evaluating its terms grouped by observations.

        Has three sub-functions which built the specific blocks of the hessian
        and one sub-function which concatenates the blocks into a full hessian.
        """

        def _aa_byobs_batched(model):
            """
            Compute the mean model diagonal block of the
            closed form hessian of base_glm_all model by observation across features
            for a batch of observations.
            """
            W = self._weight_hessian_aa(  # [observations x features]
                X=model.X,
                loc=model.mu,
                scale=model.r,
            )
            # The computation of the hessian block requires two outer products between
            # feature-wise constants and the coefficient wise design matrix entries, for each observation.
            # The resulting tensor is observations x features x coefficients x coefficients which
            # is too large too store in memory in most cases. However, the full 4D tensor is never
            # actually needed but only its marginal across features, the final hessian block shape.
            # Here, we use the einsum to efficiently perform the two outer products and the marginalisation.
            if self.constraints_loc is not None:
                XH = tf.matmul(model.design_loc, model.constraints_loc)
            else:
                XH = model.design_loc

            Hblock = tf.einsum('ofc,od->fcd',
                               tf.einsum('of,oc->ofc', W, XH),
                               XH)
            return Hblock

        def _bb_byobs_batched(model):
            """
            Compute the dispersion model diagonal block of the
            closed form hessian of base_glm_all model by observation across features.
            """
            W = self._weight_hessian_bb(  # [observations=1 x features]
                X=model.X,
                loc=model.mu,
                scale=model.r,
            )
            # The computation of the hessian block requires two outer products between
            # feature-wise constants and the coefficient wise design matrix entries, for each observation.
            # The resulting tensor is observations x features x coefficients x coefficients which
            # is too large too store in memory in most cases. However, the full 4D tensor is never
            # actually needed but only its marginal across features, the final hessian block shape.
            # Here, we use the Einstein summation to efficiently perform the two outer products and the marginalisation.
            if self.constraints_scale is not None:
                XH = tf.matmul(model.design_scale, model.constraints_scale)
            else:
                XH = model.design_scale

            Hblock = tf.einsum('ofc,od->fcd',
                               tf.einsum('of,oc->ofc', W, XH),
                               XH)
            return Hblock

        def _ab_byobs_batched(model):
            """
            Compute the mean-dispersion model off-diagonal block of the
            closed form hessian of base_glm_all model by observastion across features.

            Note that there are two blocks of the same size which can
            be compute from each other with a transpose operation as
            the hessian is symmetric.
            """
            W = self._weight_hessian_ab(  # [observations=1 x features]
                X=model.X,
                loc=model.mu,
                scale=model.r,
            )
            # The computation of the hessian block requires two outer products between
            # feature-wise constants and the coefficient wise design matrix entries, for each observation.
            # The resulting tensor is observations x features x coefficients x coefficients which
            # is too large too store in memory in most cases. However, the full 4D tensor is never
            # actually needed but only its marginal across features, the final hessian block shape.
            # Here, we use the Einstein summation to efficiently perform the two outer products and the marginalisation.
            if self.constraints_loc is not None:
                XHloc = tf.matmul(model.design_loc, model.constraints_loc)
            else:
                XHloc = model.design_loc

            if self.constraints_scale is not None:
                XHscale = tf.matmul(model.design_scale, model.constraints_scale)
            else:
                XHscale = model.design_scale

            Hblock = tf.einsum('ofc,od->fcd',
                               tf.einsum('of,oc->ofc', W, XHloc),
                               XHscale)
            return Hblock

        if self.compute_a and self.compute_b:
            H_aa = _aa_byobs_batched(model=model)
            H_bb = _bb_byobs_batched(model=model)
            H_ab = _ab_byobs_batched(model=model)
            H_ba = tf.transpose(H_ab, perm=[0, 2, 1])
            H = tf.concat(
                [tf.concat([H_aa, H_ab], axis=2),
                 tf.concat([H_ba, H_bb], axis=2)],
                axis=1
            )
        elif self.compute_a and not self.compute_b:
            H = _aa_byobs_batched(model=model)
        elif not self.compute_a and self.compute_b:
            H = _bb_byobs_batched(model=model)
        else:
            H = tf.zeros((), dtype=self.dtype)

        return H

    def hessian_tf(
            self,
            model
    ) -> tf.Tensor:
        """
        Compute hessians via tf.hessian for all gene-wise models separately.

        Contains three functions:

            - feature_wises_batch():
            a function that computes all hessians for a given batch
            of data by distributing the computation across features.
            - hessian_map():
            a function that unpacks the data from the iterator to run
            feature_wises_batch.
            - hessian_red():
            a function that performs the reduction of the hessians across hessians
            into a single hessian during the iteration over batches.
        """
        def hessian(model, params, a_split, b_split):
            """ Helper function that computes hessian for a given gene.

            :param data: tuple (X_t, size_factors_t, params_t)
            """
            if self._compute_hess_a and self._compute_hess_b:
                H = tf.hessians(model.log_likelihood, params)
            elif self._compute_hess_a and not self._compute_hess_b:
                H = tf.hessians(model.log_likelihood, a_split)
            elif not self._compute_hess_a and self._compute_hess_b:
                H = tf.hessians(model.log_likelihood, b_split)
            else:
                H = tf.zeros((), dtype=self.dtype)

            return H

        # Map hessian computation across genes
        p_shape_a = self.model_vars.a_var.shape[0]  # This has to be _var to work with constraints.
        p_shape_b = self.model_vars.b_var.shape[0]  # This has to be _var to work with constraints.
        a_split, b_split = tf.split(self.model_vars.params, tf.TensorShape([p_shape_a, p_shape_b]))
        params_t = tf.transpose(tf.expand_dims(self.model_vars.params, axis=0), perm=[2, 0, 1])
        a_split_t = tf.transpose(tf.expand_dims(a_split, axis=0), perm=[2, 0, 1])
        b_split_t = tf.transpose(tf.expand_dims(b_split, axis=0), perm=[2, 0, 1])

        hessians = tf.map_fn(
            fn=hessian,
            elems=(params_t, a_split_t, b_split_t),
            dtype=[self.dtype],
            parallel_iterations=pkg_constants.TF_LOOP_PARALLEL_ITERATIONS
        )

        hessians = [tf.squeeze(tf.squeeze(tf.stack(h), axis=2), axis=3) for h in hessians]

        return hessians[0]
