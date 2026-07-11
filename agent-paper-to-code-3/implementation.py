
import numpy as np
import math
import random

class IsolationForest:
    def __init__(self, n_estimators=100, max_samples=256):
        """
        Initializes the IsolationForest.

        Args:
            n_estimators (int): The number of iTrees to build.
            max_samples (int): The number of samples to draw from X
                                to train each base estimator.
        """
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.i_trees = []
        self.max_height = math.ceil(math.log2(max_samples)) # l = ceiling(log2(psi))

    class Node:
        """Base class for nodes in an iTree."""
        def __init__(self):
            pass

    class InternalNode(Node):
        """Represents an internal node in an iTree."""
        def __init__(self, left, right, split_attribute, split_value):
            super().__init__()
            self.left = left
            self.right = right
            self.split_attribute = split_attribute
            self.split_value = split_value

    class ExternalNode(Node):
        """Represents an external node (leaf) in an iTree."""
        def __init__(self, size):
            super().__init__()
            self.size = size

    def _c(self, n):
        """
        Calculates the average path length of an unsuccessful search in a BST,
        used for normalization of path lengths. (Equation 1 in the paper)

        Args:
            n (int): The number of instances.

        Returns:
            float: The average path length.
        """
        if n <= 1:
            return 0.0
        return 2 * (math.log(n - 1) + 0.5772156649) - (2 * (n - 1) / n)

    def _iTree(self, X, current_height):
        """
        Builds a single Isolation Tree (iTree). (Algorithm 2 in the paper)

        Args:
            X (np.ndarray): The input data (sub-sample).
            current_height (int): The current height of the tree (e).

        Returns:
            IsolationForest.Node: The root node of the constructed iTree.
        """
        if current_height >= self.max_height or len(X) <= 1 or np.all(X == X[0, :], axis=0).all():
            return self.ExternalNode(size=len(X))
        else:
            # Randomly select an attribute q
            n_features = X.shape[1]
            q = random.randint(0, n_features - 1)

            # Randomly select a split point p from max and min values of attribute q
            q_min = X[:, q].min()
            q_max = X[:, q].max()

            # Handle case where all values for attribute q are the same
            if q_min == q_max:
                return self.ExternalNode(size=len(X))

            p = random.uniform(q_min, q_max)

            # Filter data points into Xl and Xr
            Xl = X[X[:, q] < p]
            Xr = X[X[:, q] >= p]

            left_child = self._iTree(Xl, current_height + 1)
            right_child = self._iTree(Xr, current_height + 1)

            return self.InternalNode(left_child, right_child, q, p)

    def fit(self, X):
        """
        Fits the IsolationForest model. (Algorithm 1 in the paper)

        Args:
            X (np.ndarray): The input data to train the forest.
        """
        self.i_trees = []
        n_instances = len(X)

        # Set height limit l = ceiling(log2(psi))
        # self.max_height is already set in __init__ using max_samples (psi)

        for _ in range(self.n_estimators):
            # X' <- sample(X, psi)
            indices = np.random.choice(n_instances, size=min(n_instances, self.max_samples), replace=False)
            X_prime = X[indices]

            # Forest <- Forest U iTree(X', 0, l)
            self.i_trees.append(self._iTree(X_prime, 0))

    def _path_length(self, x, tree, current_path_length):
        """
        Calculates the path length for a single instance x in a given iTree.
        (Algorithm 3 in the paper)

        Args:
            x (np.ndarray): A single instance.
            tree (IsolationForest.Node): The current node in the iTree.
            current_path_length (int): The path length from the root to the current node (e).

        Returns:
            float: The path length of x.
        """
        if isinstance(tree, self.ExternalNode):
            # return e + c(T.size)
            return current_path_length + self._c(tree.size)
        else: # InternalNode
            # a <- T.splitAtt
            # if xa < T.splitValue then
            #   return PathLength(x, T.left, e + 1)
            # else {xa >= T.splitValue}
            #   return PathLength(x, T.right, e + 1)
            if x[tree.split_attribute] < tree.split_value:
                return self._path_length(x, tree.left, current_path_length + 1)
            else:
                return self._path_length(x, tree.right, current_path_length + 1)

    def predict(self, X):
        """
        Predicts anomaly scores for instances in X.

        Args:
            X (np.ndarray): The input data to predict anomaly scores for.

        Returns:
            np.ndarray: An array of anomaly scores for each instance in X.
        """
        anomaly_scores = []
        n_instances = len(X)
        
        # Calculate E(h(x)) for each instance
        expected_path_lengths = np.zeros(n_instances)
        for i, x in enumerate(X):
            total_path_length = 0
            for tree in self.i_trees:
                total_path_length += self._path_length(x, tree, 0)
            expected_path_lengths[i] = total_path_length / len(self.i_trees)

        # Calculate anomaly score s(x, n) (Equation 2 in the paper)
        # s(x,n) = 2^(-E(h(x))/c(n))
        # Here 'n' in c(n) refers to the subsampling size, psi, used during training,
        # as per the paper's discussion on normalization.
        cn_val = self._c(self.max_samples)
        
        # Avoid division by zero if cn_val is 0 (e.g., if max_samples <= 1)
        if cn_val == 0:
            # If c(n) is 0, it means the path length is effectively infinite or undefined for normalization.
            # In this edge case, if E(h(x)) is also 0, score could be 1. Otherwise, 0.
            # However, for practical purposes, max_samples will be > 1.
            # For simplicity, if cn_val is 0, we can return 0.5 as per the paper's condition s->0.5
            # when E(h(x)) -> c(n), which would imply h(x) is also 0 here.
            # A more robust solution might involve clamping or special handling but for now,
            # assuming max_samples > 1 makes cn_val > 0.
            # If it could happen, returning 0.5 is a safe default.
            anomaly_scores = np.full(n_instances, 0.5)
        else:
            anomaly_scores = 2 ** (-expected_path_lengths / cn_val)

        return anomaly_scores

# Simple test to ensure the code runs without syntax errors and basic functionality.
if __name__ == '__main__':
    # Generate some dummy data
    # 100 normal instances, 2 features
    X_normal = np.random.rand(100, 2) * 10
    # 5 anomaly instances, 2 features, far away
    X_anomaly = np.array([[0.5, 0.5], [9.5, 9.5], [0.1, 9.9], [9.9, 0.1], [5, 50]])

    X_train = np.vstack((X_normal, X_anomaly))
    np.random.shuffle(X_train) # Shuffle to mix normal and anomaly points

    print("Training Isolation Forest...")
    # Using default n_estimators=100, max_samples=256
    # Note: max_samples should be <= number of instances in X_train for non-replacement sampling to work correctly.
    # Here len(X_train) = 105, so max_samples=256 is fine, it will sample min(105, 256) = 105.
    model = IsolationForest(n_estimators=10, max_samples=100) # Reduced estimators for quicker test
    model.fit(X_train)
    print("Training complete.")

    # Predict anomaly scores
    print("Predicting anomaly scores...")
    scores = model.predict(X_train)
    print("Prediction complete.")

    # Sort instances by anomaly score to see which ones are ranked highest
    sorted_indices = np.argsort(scores)[::-1] # Descending order

    print("\nTop 10 instances with highest anomaly scores:")
    for i in sorted_indices[:10]:
        print(f"Instance: {X_train[i]}, Score: {scores[i]:.4f}")

    # For verification, we can observe if anomaly instances (from X_anomaly) tend to have higher scores.
    # It's not a rigorous test but helps sanity check.
    # The actual anomalies were X_train[100:105] before shuffling if we stacked them directly.
    # After shuffling, we'd need to keep track of original indices or test X_anomaly separately.

    # Let's test X_anomaly and X_normal separately after fitting to X_train
    print("\nScores for original anomaly points:")
    anomaly_scores = model.predict(X_anomaly)
    for i, score in enumerate(anomaly_scores):
        print(f"Anomaly {i}: {X_anomaly[i]}, Score: {score:.4f}")

    print("\nScores for original normal points (first 5):")
    normal_scores = model.predict(X_normal[:5])
    for i, score in enumerate(normal_scores):
        print(f"Normal {i}: {X_normal[i]}, Score: {score:.4f}")
