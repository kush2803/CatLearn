""" Functions to build a baseline model. """
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import numpy as np
from scipy.optimize import minimize
from math import log

from .database_functions import DescriptorDatabase
from .fpm_operations import (get_order_2, get_order_2ab, get_ablog,
                             get_div_order_2, get_labels_order_2,
                             get_labels_order_2ab, get_labels_ablog)
from .feature_select import iterative_screening, pca, lasso, clean_zero
from .feature_select import robust_rank_correlation_screening as rr_screen
from .feature_select import sure_independence_screening as sure_screen
from .fingerprint_setup import standardize
from .predict import FitnessPrediction
from .model_selection import negative_logp

from .fit_funcs import find_optimal_regularization, RR


class ModelBuilder(object):
    def __init__(self, update_train_db=True, update_test_db=True,
                 db_name='fpv_store.sqlite', screening_method='rrcs',
                 screening_correlation='kendall', initial_prediction=True,
                 clean_features=True, expand=True, optimize=True, size=None,
                 width=0.5, regularization=0.001):
        """ Function to make a best guess for a GP model that will give
            reasonable results.

            Parameters
            ----------
            update_train_db : boolean
                Set whether to write out the training feature matrix to a
                database. Default is True.
            update_test_db : boolean
                Set whether to write out the test feature matrix to a database.
                Default is False.
            db_name : string
                Name of database file.
            screening_method : string
                Method to reduce the number of features when features is
                greater than number of data points. Default is robust rank
                correlation screening.
            screening_correlation : string
                Correlation used in screening routine. Only required for rrcs.
                Default is Kendall.
            initial_prediction : boolean
                Set True to make prediction on the model first proposed, all
                original features suggested. Default is True.
            clean_features : boolean
                Remove zero distribution features if True. Default is True.
            optimize : boolean
                Allow the function to try and predict the ideal size of the
                feature matrix. Default is True.
            size : int
                If optimize is False, set the number of features to be
                returned. Will return the n best.
            width : float or list
                Starting guess for the kernel weights.
            regularization : float
                Starting guess for the noise parameter.
        """
        self.update_train_db = update_train_db
        self.update_test_db = update_test_db
        self.db_name = db_name
        self.screening_method = screening_method
        self.screening_correlation = screening_correlation
        self.initial_prediction = initial_prediction
        self.clean_features = clean_features
        self.expand = expand
        self.optimize = optimize
        self.size = size
        self.width = width
        self.regularization = regularization

    def from_atoms(self, train_atoms, fpv_function, train_target, build=True,
                   test_atoms=None, test_target=None, feature_names=None):
        """ Build model from a set of atoms objects.

            Parameters
            ----------
            train_atoms : list
                List of atoms objects on which to train the GP model.
            fpv_function : functions
                Function to take the list of atoms objects and return a set of
                features.
            train_target : list
                List of target values corresponding to the training data.
            build : boolean
                Decide whether to try and generate a best-guess model. Default
                is True.
            test_atoms : list
                List of atoms objects on which to make predictions.
            test_target : list
                List of target values corresponding to the test data if
                avaliable.
            feature_names : list
                List of names corresponding to each feature generated by the
                fpv_function.
        """
        # Generate the training feature matrix from atoms objects.
        train_matrix = fpv_function(train_atoms)
        train_id = [a.info['unique_id'] for a in train_atoms]

        # Make feature matrix for test data if atoms objects are supplied.
        test_id, test_matrix = None, None
        if test_atoms is not None:
            test_matrix = fpv_function(test_atoms)
            test_id = [a.info['unique_id'] for a in test_atoms]

        return self.from_matrix(train_matrix=train_matrix,
                                train_target=train_target,
                                feature_names=feature_names, train_id=train_id,
                                test_matrix=test_matrix, test_id=test_id,
                                test_target=test_target, build=build)

    def from_matrix(self, train_matrix, train_target, feature_names=None,
                    train_id=None, test_matrix=None, test_id=None,
                    test_target=None, build=True):
        """ Build a model from a pre-generated feature matrix.

            Parameters
            ----------
            train_matrix : matrix
                Matrix containing all the features for all candidates in the
                training dataset.
            train_id : list
                List of uuids corresponding to the atoms objects in the
                training dataset.
            test_matrix : matrix
                Matrix containing all the features for all candidates in the
                test dataset.
            test_id : list
                List of uuids corresponding to the atoms objects in the
                test dataset.
        """
        # Generate standard feature neames for basic tracking.
        if feature_names is None:
            feature_names = ['f' + str(i) for i in
                             range(len(train_matrix[0]))]

        # Update (or create) feature database.
        if self.update_train_db:
            self.db_store(type='train', atoms_id=train_id,
                          feature_matrix=train_matrix, target=train_target,
                          feature_names=feature_names,
                          table='OriginalFeatureSpace')

        if self.update_test_db:
            self.db_store(type='test', atoms_id=test_id,
                          feature_matrix=test_matrix, target=test_target,
                          feature_names=feature_names,
                          table='OriginalFeatureSpace')

        if build:
            limit = np.shape(train_matrix)[0]
            if np.shape(train_matrix)[1] < limit:
                print('Initial model will rank all features')
                limit = np.shape(train_matrix)[1]
            im = self.build_model(train_matrix=train_matrix,
                                  feature_names=feature_names,
                                  train_id=train_id, train_target=train_target,
                                  test_matrix=test_matrix, test_id=test_id,
                                  test_target=test_target,
                                  limit=limit)

        if self.expand:
            train_matrix, feature_names = self.expand_matrix(train_matrix,
                                                             feature_names)

            if self.update_train_db:
                self.db_store(type='train', atoms_id=train_id,
                              feature_matrix=train_matrix, target=train_target,
                              feature_names=feature_names,
                              table='ExpandedFeatureSpace')

            if test_matrix is not None:
                test_matrix = self.expand_matrix(test_matrix,
                                                 return_names=False)[0]

                if self.update_test_db:
                    self.db_store(type='test', atoms_id=test_id,
                                  feature_matrix=test_matrix,
                                  target=test_target,
                                  feature_names=feature_names,
                                  table='ExpandedFeatureSpace')

                if build:
                    return self.build_model(train_matrix=train_matrix,
                                            feature_names=feature_names,
                                            train_id=train_id,
                                            train_target=train_target,
                                            test_matrix=test_matrix,
                                            test_id=test_id,
                                            test_target=test_target,
                                            limit=np.shape(train_matrix)[0])

    def build_model(self, train_matrix, train_target, feature_names=None,
                    train_id=None, test_matrix=None, test_id=None,
                    test_target=None, limit=None):
        """ Build a model from a pre-generated feature matrix. """
        # Remove features with zero varience.
        c = clean_zero(train=train_matrix, test=test_matrix)
        test_matrix = c['test']
        train_matrix = c['train']
        if feature_names is not None:
            feature_names = list(np.delete(feature_names, c['index'], axis=0))
        # Standardize the feature matrix.
        std = standardize(train=train_matrix, test=test_matrix)
        test_matrix = std['test']
        train_matrix = std['train']

        if self.size is not None:
            msg = 'Feature space that is too small to be reduced to size'
            msg += ' %s. Note this is checked after the' % str(self.size)
            msg += ' matrix has been scrubbed of zero difference features.'
            assert len(train_matrix[0]) > self.size, msg

        if self.initial_prediction:
            p = self.make_prediction(train_matrix=train_matrix,
                                     test_matrix=test_matrix,
                                     train_target=train_target,
                                     test_target=test_target, opt_h=False)

            print('Initial Model:', p['validation_rmse']['average'])

        return self.reduce_matrix(train_matrix=train_matrix,
                                  test_matrix=test_matrix,
                                  train_target=train_target,
                                  test_target=test_target,
                                  feature_names=feature_names, limit=limit)

    def make_prediction(self, train_matrix, test_matrix, train_target,
                        test_target=None, opt_h=False):
        """ Function to make predictions for a given model.

            Parameters
            ----------
            width : float or list
                Set the kernel width.
            regularization : float
               Set the smoothing function.
        """
        # NOTE: Doesn't make sense to require dict, test never used?
        sf = {'train': train_matrix, 'test': test_matrix}
        if opt_h:
            w, r = self.hyp_opt(features=sf, train_target=train_target,
                                width=self.width, reg=self.regularization)
            self.width, self.regularization = w, r

        predict = FitnessPrediction(ktype='gaussian', kwidth=self.width,
                                    regularization=self.regularization)

        return predict.get_predictions(train_fp=train_matrix,
                                       test_fp=test_matrix,
                                       train_target=train_target, cinv=None,
                                       test_target=test_target,
                                       uncertainty=False, basis=None,
                                       get_validation_error=True,
                                       get_training_error=True,
                                       standardize_target=False)

    def basis(self, descriptors):
        """ Simple linear basis. """
        linear = descriptors * ([1] * len(descriptors))
        return linear

    def hyp_opt(self, features, train_target):
        """ Function to do the hyperparameter optimization. """
        # Hyper parameter starting guesses.
        m = np.shape(features['train'])[1]
        sigma = np.ones(m)
        sigma *= self.width
        theta = np.append(sigma, self.regularization)

        a = (features, train_target)

        # Hyper parameter bounds.
        b = ((1E-9, None), ) * (m+1)

        # Do the optimization.
        popt = minimize(negative_logp, theta, args=a, bounds=b)['x']

        return popt[:-1], popt[-1:]

    def expand_matrix(self, feature_matrix, feature_names=None,
                      return_names=True):
        """ Expand the feature matrix by combing original features. """
        # Extend the feature matrix combinatorially.
        order_2 = get_order_2(feature_matrix)
        div_order_2 = get_div_order_2(feature_matrix)
        order_2ab = get_order_2ab(feature_matrix, a=2, b=4)
        ablog = get_ablog(feature_matrix, a=2, b=4)

        feature_matrix = np.concatenate((feature_matrix, order_2, div_order_2,
                                         order_2ab, ablog), axis=1)

        if return_names:
            # Extend the feature naming scheme.
            order_2 = get_labels_order_2(feature_names)
            div_order_2 = get_labels_order_2(feature_names, div=True)
            order_2ab = get_labels_order_2ab(feature_names, a=2, b=4)
            ablog = get_labels_ablog(feature_names, a=2, b=4)
            feature_names += order_2 + div_order_2 + order_2ab + ablog

        return feature_matrix, feature_names

    def reduce_matrix(self, train_matrix, train_target, feature_names,
                      test_matrix=None, test_target=None, limit=None):
        """ Function to reduce the feature space. """
        # Check to see if there are more features than data points.
        n = np.shape(train_matrix)[0]
        d = np.shape(train_matrix)[1]

        if limit is not None:
            assert limit <= d

        if d > n:
            sf = self.screening(train_matrix=train_matrix,
                                train_target=train_target,
                                test_matrix=test_matrix,
                                test_target=test_target,
                                feature_names=feature_names)
            train_matrix, test_matrix, feature_names = sf

        # Find importance of features andtrain a ridge regression model.
        linear = self.ridge_regression(train_matrix=train_matrix,
                                       train_target=train_target,
                                       test_matrix=test_matrix,
                                       test_target=test_target,
                                       feature_names=feature_names)
        coefs, linear_error = linear[0][0], linear[1]
        order, feature_names = linear[0][1], linear[0][2]

        ml, mf, mo = self.lasso_opt(size=d, train_target=train_target,
                                    train_matrix=train_matrix,
                                    test_matrix=test_matrix,
                                    test_target=test_target,
                                    alpha=1.e-1, max_iter=1e6, steps=20)

        print(feature_names)
        best_size = self.size

        if self.optimize:
            if limit is None:
                limit = n
            best_p1 = float('inf')
            for s in range(1, limit + 1):
                # remove_features = order[s:]
                remove_features = mo[s:]
                reduced_train = np.delete(train_matrix, remove_features,
                                          axis=1)
                reduced_test = np.delete(test_matrix, remove_features, axis=1)

                p = self.make_prediction(train_matrix=reduced_train,
                                         test_matrix=reduced_test,
                                         train_target=train_target,
                                         test_target=test_target)

                if p['validation_rmse']['average'] < best_p1:
                    best_p1, best_size = p['validation_rmse']['average'], s

                if s > 1:
                    pcar = self.pca_opt(max_comp=s, train_matrix=reduced_train,
                                        test_matrix=reduced_test,
                                        train_target=train_target,
                                        test_target=test_target)
                    best_pca, cc, cs = pcar

            print('max features:', len(train_matrix[0]))
            print('Best error:', best_p1, 'from', best_size, 'features',
                  '\nPCA Error:', best_pca, 'with', cc, 'components from', cs,
                  'features\nLinear Regression Error:', linear_error,
                  '\nLasso Error:', ml, 'for', mf, 'features')

        remove_features = mo[best_size:]
        train_matrix = np.delete(train_matrix, remove_features, axis=1)
        if test_matrix is not None:
            test_matrix = np.delete(test_matrix, remove_features, axis=1)

        return feature_names, train_matrix, test_matrix

    def screening(self, train_matrix, train_target, feature_names,
                  test_matrix=None, test_target=None):
        """ Function to perform the sure screening. If the number of features
            is greater than twize the size of data, the iterative function is
            used.
        """
        # Use correlation screening to reduce features down to number
        # of data.
        n = np.shape(train_matrix)[0]
        d = np.shape(train_matrix)[1]
        s = int(round(log(d/n)**0.5, 0))
        if s == 0:
            s = 1

        if d > 2 * n:
            screen = iterative_screening(target=train_target,
                                         train_fpv=train_matrix,
                                         test_fpv=test_matrix, size=n, step=s,
                                         method=self.screening_method,
                                         corr=self.screening_correlation,
                                         feature_names=feature_names,
                                         cleanup=False)
        else:
            if self.screening_method is 'rrcs':
                screen = rr_screen(target=train_target, train_fpv=train_matrix,
                                   size=n, corr=self.screening_correlation,
                                   writeout=False)
            elif self.screening_method is 'sis':
                screen = sure_screen(target=train_target,
                                     train_fpv=train_matrix, size=n,
                                     writeout=False)

        # Update the feature matrix.
        train_matrix = np.delete(train_matrix, screen['rejected'], axis=1)
        if test_matrix is not None:
            test_matrix = np.delete(test_matrix, screen['rejected'], axis=1)
        feature_names = list(np.delete(feature_names, screen['rejected'],
                                       axis=0))

        return np.asarray(train_matrix), np.asarray(test_matrix), feature_names

    def pca_opt(self, max_comp, train_matrix, test_matrix, train_target,
                test_target):
        """ Function to do the PCA optimization.

            Parameters
            ----------
            max_comp : int
                Limit of components to include.
        """
        best_pca = float('inf')
        for c in range(1, max_comp):
            comp = pca(components=c, train_fpv=train_matrix,
                       test_fpv=test_matrix)

            pc = self.make_prediction(train_matrix=comp['train_fpv'],
                                      test_matrix=comp['test_fpv'],
                                      train_target=train_target,
                                      test_target=test_target)

            if pc['validation_rmse']['average'] < best_pca:
                best_pca = pc['validation_rmse']['average']
                cc, cs = c, max_comp

        return best_pca, cc, cs

    def ridge_regression(self, train_matrix, train_target, feature_names,
                         test_matrix=None, test_target=None):
        """ Function to trean a linear ridge regression model. The importance
            of features is calculated from the coefficients.
        """
        # Ridge regression to get ordering of features.
        target = np.asarray(train_target)
        b = find_optimal_regularization(X=train_matrix, Y=target, p=0, Ns=100)
        coef = RR(X=train_matrix, Y=target, p=0, omega2=b, W2=None, Vh=None)[0]

        if test_matrix is not None:
            # Test the model.
            sumd = 0.
            for i, j in zip(test_matrix, test_target):
                sumd += (np.dot(coef, i) - j) ** 2
            error = (sumd / len(test_matrix)) ** 0.5

        order = list(range(len(coef)))
        sort_list = [list(i) for i in zip(*sorted(zip(abs(coef), order,
                                                      feature_names),
                                                  key=lambda x: x[0],
                                                  reverse=True))]

        return sort_list, error

    def lasso_opt(self, size, train_target, train_matrix, test_matrix=None,
                  test_target=None, alpha=1.e-5, max_iter=1e5, steps=None):
        """ Function to perform lasso selection of features. """
        las = lasso(size=size, target=train_target, train_matrix=train_matrix,
                    test_matrix=test_matrix, alpha=alpha, max_iter=max_iter,
                    test_target=test_target, steps=steps)
        ml = min(las['linear_error'])
        mf = las['min_features']
        mo = las['order']

        return ml, mf, mo

    def db_store(self, type, atoms_id, feature_matrix, target,
                 feature_names, table):
        """ Function to automatically store feature matrix.

            Parameters
            ----------
            type : string
                Set the name of the data to be stored, e.g. train.
            atoms_id : list
                The UUIDs for the corresponding atoms objects.
            feature_matrix : array
                An n x d array containing all of the numeric feature values.
            target : list
                A list of all the target values.
            feature_names : list
                A list of all the feature names.
            table : string
                The table name that data should be added to. Different tables
                are used to store the original and extended feature sets.
        """
        # Add on the id and target values.
        atoms_id = [[i] for i in atoms_id]
        dmat = np.append(atoms_id, feature_matrix, axis=1)
        target = [[i] for i in target]
        dmat = np.append(dmat, target, axis=1)

        dnames = feature_names + ['target']

        # Define database parameters to store features.
        new_db = DescriptorDatabase(db_name=type + '_' + self.db_name,
                                    table=table)
        new_db.create_db(names=dnames)
        new_db.fill_db(descriptor_names=dnames, data=dmat)
