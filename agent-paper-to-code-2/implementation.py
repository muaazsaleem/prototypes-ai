
import math
import random

# Define node classes for the Isolation Tree
class IsolationTreeNode:
    def __init__(self):
        self.left = None
        self.right = None
        self.split_attribute_index = None # Use index instead of name
        self.split_value = None
        self.size = 0 # For external nodes

class IsolationTreeExternalNode(IsolationTreeNode):
    def __init__(self, size):
        super().__init__()
        self.size = size

class IsolationTreeInternalNode(IsolationTreeNode):
    def __init__(self, left, right, split_attribute_index, split_value):
        super().__init__()
        self.left = left
        self.right = right
        self.split_attribute_index = split_attribute_index
        self.split_value = split_value

# Equation 1: c(n) - average path length of unsuccessful search in BST
def c(n):
    if n <= 1:
        return 0.0
    euler_constant = 0.5772156649
    return 2 * (math.log(n - 1) + euler_constant) - (2 * (n - 1) / n)

# Algorithm 3: PathLength (x, T, e)
def path_length(x, T, e):
    if isinstance(T, IsolationTreeExternalNode):
        return e + c(T.size)
    
    # x is expected to be a list of numerical values
    # T.split_attribute_index is the index of the attribute to split on
    if T.split_attribute_index >= len(x):
        raise ValueError(f"Split attribute index {T.split_attribute_index} out of bounds for instance with {len(x)} features.")

    if x[T.split_attribute_index] < T.split_value:
        return path_length(x, T.left, e + 1)
    else:
        return path_length(x, T.right, e + 1)

# Algorithm 2: iTree (X, e, l)
# X is expected to be a list of lists (instances)
def i_tree(X, e, l):
    if e >= l or len(X) <= 1:
        return IsolationTreeExternalNode(size=len(X))
    
    # Check if all data in X have the same values
    # This is more robustly checked by comparing each instance to the first one.
    if len(X) > 0:
        first_instance = X[0]
        all_same = True
        for i in range(1, len(X)):
            if X[i] != first_instance:
                all_same = False
                break
        if all_same:
            return IsolationTreeExternalNode(size=len(X))

    num_features = len(X[0]) # Assuming all instances have the same number of features
    q = random.randrange(num_features) # Randomly select an attribute index
    
    # Find min and max values for the selected attribute
    min_val = X[0][q]
    max_val = X[0][q]
    for instance in X:
        if instance[q] < min_val:
            min_val = instance[q]
        if instance[q] > max_val:
            max_val = instance[q]

    # If min_val and max_val are the same, no split is possible for this attribute
    if min_val == max_val:
        return IsolationTreeExternalNode(size=len(X))

    p = random.uniform(min_val, max_val)

    Xl = []
    Xr = []
    for instance in X:
        if instance[q] < p:
            Xl.append(instance)
        else:
            Xr.append(instance)

    if len(Xl) == 0:
        return i_tree(Xr, e + 1, l)
    if len(Xr) == 0:
        return i_tree(Xl, e + 1, l)

    left_child = i_tree(Xl, e + 1, l)
    right_child = i_tree(Xr, e + 1, l)
    
    return IsolationTreeInternalNode(left_child, right_child, q, p)

# Algorithm 1: iForest (X, t, psi)
# X is expected to be a list of lists (instances)
def i_forest(X, t, psi):
    forest = []
    l = int(math.ceil(math.log2(psi))) if psi > 1 else 1

    for _ in range(t):
        # Sample X' from X with size psi
        if len(X) <= psi:
            X_prime = list(X) # Use the entire dataset if smaller or equal to psi
        else:
            X_prime = random.sample(X, psi)
        
        tree = i_tree(X_prime, 0, l)
        forest.append(tree)
    return forest

# Equation 2: Anomaly Score s(x, n)
def anomaly_score(E_h_x, n_in_c):
    if n_in_c <= 1:
        return 0.5 
    
    denominator = c(n_in_c)
    if denominator == 0:
        return 0.5

    return 2 ** (-E_h_x / denominator)

# Main Isolation Forest class
class IsolationForest:
    def __init__(self, n_estimators=100, max_samples=256, random_state=None):
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.forest = []
        self.num_features = 0
        if random_state is not None:
            random.seed(random_state)

    def fit(self, X):
        # X is expected to be a list of lists
        if not X: # Handle empty input
            raise ValueError("Input data X cannot be empty.")
        if not isinstance(X[0], list):
             raise ValueError("Input data X must be a list of lists.")

        self.num_features = len(X[0])
        self.forest = i_forest(X, self.n_estimators, self.max_samples)

    def predict(self, X):
        # X is expected to be a list of lists
        if not X: # Handle empty input
            return []
        if not isinstance(X[0], list):
             raise ValueError("Input data X must be a list of lists.")
        if len(X[0]) != self.num_features:
            raise ValueError("Test data instances must have the same number of features as training data.")

        scores = []
        for instance in X:
            avg_path_length = 0
            for tree in self.forest:
                avg_path_length += path_length(instance, tree, 0)
            avg_path_length /= self.n_estimators
            scores.append(anomaly_score(avg_path_length, self.max_samples))

        return scores

# Test cases
if __name__ == '__main__':
    # 1. Simple 2D data
    print("Testing with simple 2D data...")
    # Normal data points (cluster around (0,0))
    X_normal = [[random.gauss(0, 0.1), random.gauss(0, 0.1)] for _ in range(100)]
    # Anomaly data points (far from the cluster)
    X_anomaly = [[5, 5], [-5, -5], [0.1, 0.1]]

    X_train = X_normal + X_anomaly
    random.shuffle(X_train) # Shuffle to mix normal and anomalies

    # Train Isolation Forest
    iforest = IsolationForest(n_estimators=10, max_samples=32, random_state=42)
    iforest.fit(X_train)

    # Predict anomaly scores for training data
    scores_train = iforest.predict(X_train)
    
    # Separate scores for original anomalies and normal points for assertion
    scores_normal = []
    scores_anomalies = []
    for i, x in enumerate(X_train):
        if x in X_normal:
            scores_normal.append(scores_train[i])
        elif x in X_anomaly:
            scores_anomalies.append(scores_train[i])

    print(f"Min score: {min(scores_train):.4f}, Max score: {max(scores_train):.4f}")
    
    # Expect anomalies to have higher scores (closer to 1)
    print("Scores for anomalies (expected high):", [f'{s:.4f}' for s in scores_anomalies])
    print("Average score for normal points (expected lower):", f'{sum(scores_normal)/len(scores_normal):.4f}')

    # Check if anomaly scores are generally higher (allowing for some randomness)
    # A strict assertion might fail due to randomness, so we can check if the average anomaly score is higher.
    assert sum(scores_anomalies) / len(scores_anomalies) > sum(scores_normal) / len(scores_normal), "Anomalies should have higher average scores"
    print("Assertion passed: Anomalies generally have higher average scores.")

    # 2. Test with all identical data points (should result in external nodes immediately)
    print("\nTesting with all identical data points...")
    X_identical = [[1, 2], [1, 2], [1, 2], [1, 2]]
    iforest_identical = IsolationForest(n_estimators=5, max_samples=4, random_state=42)
    iforest_identical.fit(X_identical)
    scores_identical = iforest_identical.predict(X_identical)
    print("Scores for identical data points (expected around 0.5):")
    print([f'{s:.4f}' for s in scores_identical])
    # All scores should be very close to 0.5
    for score in scores_identical:
        assert abs(score - 0.5) < 0.1, "Scores for identical data should be around 0.5"
    print("Assertion passed: Scores for identical data are around 0.5.")

    # 3. Test with small dataset (len(X) < max_samples)
    print("\nTesting with small dataset (len(X) < max_samples)...")
    X_small = [[random.random(), random.random(), random.random()] for _ in range(5)]
    iforest_small = IsolationForest(n_estimators=5, max_samples=10, random_state=42)
    iforest_small.fit(X_small)
    scores_small = iforest_small.predict(X_small)
    print("Scores for small dataset:")
    print([f'{s:.4f}' for s in scores_small])
    print("\nAll tests completed successfully.")

