
import numpy as np
import random
import math

# Euler-Mascheroni constant
EULER_MASCHERONI = 0.5772156649

class Node:
    """Base class for nodes in an Isolation Tree."""
    pass

class ExternalNode(Node):
    """Represents an external node (leaf) in an Isolation Tree."""
    def __init__(self, size):
        self.size = size

class InternalNode(Node):
    """Represents an internal node in an Isolation Tree."""
    def __init__(self, left, right, split_attribute, split_value):
        self.left = left
        self.right = right
        self.split_attribute = split_attribute
        self.split_value = split_value

def c(n):
    """
    Calculates the average path length of an unsuccessful search in a Binary Search Tree.
    Used for normalizing path lengths in Isolation Forest.
    Equation 1 from the paper.
    """
    if n <= 1:
        return 0
    return 2 * (math.log(n - 1) + EULER_MASCHERONI) - (2 * (n - 1) / n)

def iTree(X, e, l):
    """
    Algorithm 2: Builds a single Isolation Tree.
    
    Args:
        X (np.ndarray): The input data (sub-sample).
        e (int): Current tree height.
        l (int): Height limit for the tree.
        
    Returns:
        Node: The root node of the constructed iTree.
    """
    if e >= l or X.shape[0] <= 1 or np.all(X == X[0], axis=0).all():
        return ExternalNode(size=X.shape[0])
    else:
        num_attributes = X.shape[1]
        
        # Randomly select an attribute q
        q = random.randint(0, num_attributes - 1)
        
        # Randomly select a split point p
        # from max and min values of attribute q in X
        min_val = X[:, q].min()
        max_val = X[:, q].max()
        
        if min_val == max_val: # All values are the same for this attribute, cannot split
            return ExternalNode(size=X.shape[0])

        p = random.uniform(min_val, max_val)
        
        # Filter data into left and right branches
        Xl = X[X[:, q] < p]
        Xr = X[X[:, q] >= p]
        
        return InternalNode(
            left=iTree(Xl, e + 1, l),
            right=iTree(Xr, e + 1, l),
            split_attribute=q,
            split_value=p
        )

def iForest(X, t, psi):
    """
    Algorithm 1: Builds an ensemble of Isolation Trees (Isolation Forest).
    
    Args:
        X (np.ndarray): The input data for training.
        t (int): Number of trees to build.
        psi (int): Sub-sampling size.
        
    Returns:
        list: A list of t constructed iTrees.
    """
    forest = []
    # Set height limit l = ceiling(log2(psi))
    l = math.ceil(math.log2(psi)) if psi > 1 else 1
    
    for _ in range(t):
        # X_prime <- sample(X, psi)
        # Ensure we don't try to sample more instances than available
        sample_size = min(psi, X.shape[0])
        indices = random.sample(range(X.shape[0]), sample_size)
        X_prime = X[indices]
        
        forest.append(iTree(X_prime, 0, l))
        
    return forest

def PathLength(x, T, e):
    """
    Algorithm 3: Calculates the path length for a single instance in an iTree.
    
    Args:
        x (np.ndarray): The instance for which to calculate the path length.
        T (Node): The current node in the iTree (root when first called).
        e (int): Current path length (initialized to zero when first called).
        
    Returns:
        float: The path length of the instance x.
    """
    if isinstance(T, ExternalNode):
        # return e + c(T.size) {c(.) is defined in Equation 1}
        return e + c(T.size)
    
    # T is an InternalNode
    a = T.split_attribute
    
    if x[a] < T.split_value:
        return PathLength(x, T.left, e + 1)
    else: # x[a] >= T.split_value
        return PathLength(x, T.right, e + 1)

def anomaly_score(E_h_x, n):
    """
    Equation 2: Calculates the anomaly score for an instance.
    
    Args:
        E_h_x (float): The average path length of the instance from a collection of iTrees.
        n (int): The number of instances in the sub-sample (psi).
        
    Returns:
        float: The anomaly score s(x, n).
    """
    if n <= 1: # Handle edge case where c(n) is 0 or undefined
        return 0.5 if E_h_x == 0 else 0.0 # If E_h_x is also 0, it means it was an external node of size 1, so normal.
    
    cn = c(n)
    if cn == 0: # Avoid division by zero, can happen if n=1
        return 0.5
    return 2 ** (-E_h_x / cn)

class IsolationForest:
    """
    Main Isolation Forest class.
    """
    def __init__(self, n_estimators=100, sample_size=256, random_state=None):
        self.n_estimators = n_estimators
        self.sample_size = sample_size
        self.forest = []
        if random_state is not None:
            random.seed(random_state)
            np.random.seed(random_state)

    def fit(self, X):
        """
        Fits the Isolation Forest model.
        
        Args:
            X (np.ndarray): The training data.
        """
        self.forest = iForest(X, self.n_estimators, self.sample_size)
        
    def predict(self, X):
        """
        Predicts anomaly scores for the given instances.
        
        Args:
            X (np.ndarray): The instances to predict.
            
        Returns:
            np.ndarray: An array of anomaly scores for each instance.
        """
        if not self.forest:
            raise RuntimeError("Isolation Forest not fitted. Call fit() first.")
            
        scores = []
        for x_instance in X:
            path_lengths = []
            for tree in self.forest:
                path_lengths.append(PathLength(x_instance, tree, 0))
            
            # E(h(x)) is the average of h(x) from a collection of isolation trees
            E_h_x = np.mean(path_lengths)
            scores.append(anomaly_score(E_h_x, self.sample_size))
            
        return np.array(scores)

# Example usage (for testing)
if __name__ == "__main__":
    # Generate some synthetic data
    # Normal points (cluster 1)
    X_normal_1 = np.random.normal(loc=[0, 0], scale=1, size=(100, 2))
    # Normal points (cluster 2)
    X_normal_2 = np.random.normal(loc=[5, 5], scale=1, size=(100, 2))
    
    # Anomalies
    X_anomalies = np.random.uniform(low=-10, high=10, size=(10, 2))
    
    X_train = np.vstack([X_normal_1, X_normal_2])
    X_test = np.vstack([X_normal_1, X_normal_2, X_anomalies])

    print("Training data shape:", X_train.shape)
    print("Testing data shape:", X_test.shape)

    # Initialize and fit Isolation Forest
    # Using default values from the paper: t=100, psi=256
    iforest_model = IsolationForest(n_estimators=100, sample_size=256, random_state=42)
    iforest_model.fit(X_train)

    # Predict anomaly scores
    scores = iforest_model.predict(X_test)

    # Sort instances by anomaly score (higher score means more anomalous)
    sorted_indices = np.argsort(scores)[::-1]
    
    print("\nTop 10 instances with highest anomaly scores:")
    for i in sorted_indices[:10]:
        is_anomaly_in_test = "Anomaly" if i >= (X_normal_1.shape[0] + X_normal_2.shape[0]) else "Normal"
        print(f"Instance {i}: {X_test[i]}, Score: {scores[i]:.4f}, Type: {is_anomaly_in_test}")

    # Check average scores for known normal vs anomaly points
    print("\nAverage score for normal points (from test set):", np.mean(scores[:X_normal_1.shape[0] + X_normal_2.shape[0]]))
    print("Average score for anomaly points (from test set):", np.mean(scores[X_normal_1.shape[0] + X_normal_2.shape[0]:]))
