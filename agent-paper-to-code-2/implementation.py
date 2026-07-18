
import math
import random

class ExNode:
    """Represents an external node in an Isolation Tree."""
    def __init__(self, size):
        self.size = size

class InNode:
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
        return 0.0
    return 2 * (math.log(n - 1) + 0.5772156649) - (2 * (n - 1) / n)

def PathLength(x, T, e):
    """
    Calculates the path length of an instance x in an Isolation Tree T.
    Algorithm 3 from the paper.
    """
    if isinstance(T, ExNode):
        return e + c(T.size)
    
    # x is expected to be a list/tuple, T.split_attribute is an index
    if x[T.split_attribute] < T.split_value:
        return PathLength(x, T.left, e + 1)
    else:
        return PathLength(x, T.right, e + 1)

def iTree(X, current_height, height_limit):
    """
    Builds a single Isolation Tree.
    Algorithm 2 from the paper.
    X: Input data (list of lists).
    """
    if current_height >= height_limit or len(X) <= 1:
        return ExNode(len(X))
    
    num_attributes = len(X[0]) # Assuming X is not empty and all rows have same number of attributes
    
    # Randomly select an attribute
    q = random.randint(0, num_attributes - 1)
    
    # Get values for the selected attribute
    attribute_values = [row[q] for row in X]
    
    # Randomly select a split point p
    min_val = min(attribute_values)
    max_val = max(attribute_values)

    # Handle the case where all values for the selected attribute are the same
    if min_val == max_val:
        return ExNode(len(X))

    p = random.uniform(min_val, max_val)
    
    # Partition the data
    Xl = [row for row in X if row[q] < p]
    Xr = [row for row in X if row[q] >= p]

    # Handle cases where one partition is empty
    if len(Xl) == 0:
        return iTree(Xr, current_height + 1, height_limit)
    if len(Xr) == 0:
        return iTree(Xl, current_height + 1, height_limit)

    left_child = iTree(Xl, current_height + 1, height_limit)
    right_child = iTree(Xr, current_height + 1, height_limit)
    
    return InNode(left_child, right_child, q, p)

class IsolationForest:
    """
    Implements the Isolation Forest algorithm.
    Algorithms 1 and 2 from the paper.
    """
    def __init__(self, num_trees=100, subsample_size=256):
        self.num_trees = num_trees
        self.subsample_size = subsample_size
        self.forest = []
        self.height_limit = math.ceil(math.log2(subsample_size))

    def fit(self, X):
        """
        Trains the Isolation Forest.
        X: Input data (list of lists).
        """
        self.forest = []
        n_samples = len(X)

        for _ in range(self.num_trees):
            # Sub-sample the data (without replacement)
            if self.subsample_size > n_samples:
                # If subsample_size is greater than n_samples, use all samples
                X_sample = list(X) # Make a copy
            else:
                X_sample = random.sample(X, self.subsample_size)
            
            tree = iTree(X_sample, 0, self.height_limit)
            self.forest.append(tree)

    def decision_function(self, X):
        """
        Calculates the average path length for each instance in X.
        X: Input data (list of lists).
        Returns a list of average path lengths.
        """
        if not self.forest:
            raise RuntimeError("Isolation Forest has not been fitted.")

        path_lengths = [0.0] * len(X)
        
        for i, instance in enumerate(X):
            h_x_sum = 0
            for tree in self.forest:
                h_x_sum += PathLength(instance, tree, 0)
            path_lengths[i] = h_x_sum / self.num_trees
            
        return path_lengths

    def predict(self, X):
        """
        Calculates the anomaly score for each instance in X.
        Equation 2 from the paper.
        X: Input data (list of lists).
        Returns a list of anomaly scores.
        """
        if not self.forest:
            raise RuntimeError("Isolation Forest has not been fitted.")
        
        avg_path_lengths = self.decision_function(X)
        
        # Original paper used subsample_size 'n' in c(n), so we use that here.
        # This 'n' corresponds to the sub-sampling size 'psi' (ψ) used to build the trees.
        c_val = c(self.subsample_size)

        # Anomaly score s(x, n) = 2^(-E(h(x))/c(n))
        scores = [2 ** (-h_x / c_val) for h_x in avg_path_lengths]
        return scores

# Example Usage (for testing purposes)
if __name__ == "__main__":
    # Generate some synthetic data using random module
    # Normal points (cluster 1)
    random.seed(42)
    X_normal_1 = []
    for _ in range(200):
        X_normal_1.append([random.gauss(2, 0.5), random.gauss(2, 0.5)])
    
    # Normal points (cluster 2)
    X_normal_2 = []
    for _ in range(200):
        X_normal_2.append([random.gauss(-2, 0.5), random.gauss(-2, 0.5)])
    
    # Anomalies
    X_anomalies = []
    for _ in range(20):
        X_anomalies.append([random.uniform(-6, 6), random.uniform(-6, 6)])

    X_train = X_normal_1 + X_normal_2 + X_anomalies
    random.shuffle(X_train)

    # Create and fit Isolation Forest
    iforest = IsolationForest(num_trees=100, subsample_size=256)
    iforest.fit(X_train)

    # Generate some test data
    X_test_normal = []
    for _ in range(50):
        X_test_normal.append([random.gauss(2, 0.5), random.gauss(2, 0.5)])

    X_test_anomaly = []
    for _ in range(5):
        X_test_anomaly.append([random.uniform(-8, 8), random.uniform(-8, 8)])

    X_test = X_test_normal + X_test_anomaly

    # Get anomaly scores
    anomaly_scores = iforest.predict(X_test)

    print("Anomaly Scores for test instances:")
    for i, score in enumerate(anomaly_scores):
        if i < len(X_test_normal):
            print(f"Normal point {i+1}: {score:.4f}")
        else:
            print(f"Anomaly point {i - len(X_test_normal) + 1}: {score:.4f} (Expected high)")

    # Sort and identify top anomalies (manually for lists)
    # Create a list of (score, index) tuples, then sort by score descending
    scored_instances = [(score, i, X_test[i]) for i, score in enumerate(anomaly_scores)]
    scored_instances.sort(key=lambda x: x[0], reverse=True)

    print("\nTop 5 anomalies (highest scores):")
    for i in range(min(5, len(scored_instances))):
        score, idx, data = scored_instances[i]
        print(f"Instance {idx}: Score = {score:.4f}, Data = {data}")

    # Test with a single point
    single_point_anomaly = [10.0, 10.0]
    single_score_anomaly = iforest.predict([single_point_anomaly])
    print(f"\nScore for single anomalous point {single_point_anomaly}: {single_score_anomaly[0]:.4f}")

    single_point_normal = [2.0, 2.0]
    single_score_normal = iforest.predict([single_point_normal])
    print(f"Score for single normal point {single_point_normal}: {single_score_normal[0]:.4f}")
