
import random
import math

class IsolationTree:
    def __init__(self, left=None, right=None, split_attribute=None, split_value=None, size=0, is_external=False):
        self.left = left
        self.right = right
        self.split_attribute = split_attribute # Index of the attribute
        self.split_value = split_value
        self.size = size
        self.is_external = is_external

def c_factor(n):
    """
    Calculates the average path length of an unsuccessful search in a Binary Search Tree.
    Used for path length normalization.
    Equation 1 from the paper.
    """
    if n > 2:
        return 2 * (math.log(n - 1) + 0.5772156649) - (2 * (n - 1) / n)
    elif n == 2:
        return 1
    else: # n <= 1
        return 0

def path_length(x, tree, current_path_length):
    """
    Calculates the path length for a single instance x in a given IsolationTree.
    Algorithm 3 from the paper.
    x is a list/tuple representing an instance.
    """
    if tree.is_external:
        return current_path_length + c_factor(tree.size)
    
    a = tree.split_attribute
    if x[a] < tree.split_value:
        return path_length(x, tree.left, current_path_length + 1)
    else:
        return path_length(x, tree.right, current_path_length + 1)

def iTree(X, current_height, height_limit):
    """
    Builds a single Isolation Tree.
    Algorithm 2 from the paper.
    X is a list of lists/tuples.
    """
    if current_height >= height_limit or len(X) <= 1:
        return IsolationTree(size=len(X), is_external=True)
    
    num_attributes = len(X[0]) # Assuming all instances have the same number of attributes
    
    # Randomly select an attribute q (index)
    q = random.randint(0, num_attributes - 1)
    
    # Get min and max values for the selected attribute
    min_val = float('inf')
    max_val = float('-inf')
    for instance in X:
        if instance[q] < min_val:
            min_val = instance[q]
        if instance[q] > max_val:
            max_val = instance[q]

    # Handle cases where all values are the same for the selected attribute
    if min_val == max_val:
        return IsolationTree(size=len(X), is_external=True)
        
    p = random.uniform(min_val, max_val)
    
    # Filter data into left and right branches
    Xl = [instance for instance in X if instance[q] < p]
    Xr = [instance for instance in X if instance[q] >= p]

    # Handle cases where one side is empty after split.
    # This means the split was ineffective for this data subset.
    # In such cases, we continue building the tree with the non-empty subset.
    if len(Xl) == 0:
        return iTree(Xr, current_height + 1, height_limit)
    if len(Xr) == 0:
        return iTree(Xl, current_height + 1, height_limit)
    
    left_child = iTree(Xl, current_height + 1, height_limit)
    right_child = iTree(Xr, current_height + 1, height_limit)
    
    return IsolationTree(left=left_child, right=right_child, 
                           split_attribute=q, split_value=p, 
                           is_external=False)

def iForest(X, num_trees, subsample_size):
    """
    Builds an Isolation Forest.
    Algorithm 1 from the paper.
    X is a list of lists/tuples.
    """
    forest = []
    # height_limit l = ceiling(log2(subsample_size))
    height_limit = math.ceil(math.log(subsample_size, 2))
    
    data_size = len(X)

    for _ in range(num_trees):
        # X' <- sample(X, psi)
        # Randomly sample without replacement
        X_prime = random.sample(X, subsample_size)
        tree = iTree(X_prime, 0, height_limit)
        forest.append(tree)
        
    return forest

def calculate_anomaly_scores(X, forest, subsample_size):
    """
    Calculates anomaly scores for each instance in X using the given Isolation Forest.
    Equation 2 from the paper.
    X is a list of lists/tuples.
    """
    anomaly_scores = []
    # c(n) is for the average path length of *subsample_size* items
    # so use subsample_size for the c_factor calculation, not the full dataset size.
    c_n = c_factor(subsample_size)
    
    for x in X:
        path_lengths = []
        for tree in forest:
            path_lengths.append(path_length(x, tree, 0))
        
        # E(h(x)) is the average of h(x) from a collection of isolation trees
        avg_path_length = sum(path_lengths) / len(path_lengths)
        
        # s(x, n) = 2^(-E(h(x))/c(n))
        score = 2 ** (-avg_path_length / c_n)
        anomaly_scores.append(score)
        
    return anomaly_scores

# Example Usage (for testing purposes)
if __name__ == "__main__":
    # Generate some sample data
    random.seed(42)
    data = [[random.uniform(0, 10), random.uniform(0, 10)] for _ in range(100)]
    # Add a few anomalies
    data.extend([[1.0, 1.0], [9.0, 9.0], [0.0, 5.0], [5.0, 0.0]])

    num_trees = 100
    subsample_size = 32

    # Train the iForest
    forest = iForest(data, num_trees, subsample_size)

    # Calculate anomaly scores
    scores = calculate_anomaly_scores(data, forest, subsample_size)

    print("Anomaly Scores (first 10, then anomalies):")
    print(scores[:10])
    print(scores[100:])

    # Identify top anomalies
    # Create a list of (score, index) tuples for sorting
    indexed_scores = [(scores[i], i) for i in range(len(scores))]
    indexed_scores.sort(key=lambda x: x[0], reverse=True)

    print('\nTop 5 anomalies (indices and scores):')
    for i in range(5):
        score, original_index = indexed_scores[i]
        print(f"Index: {original_index}, Score: {score:.4f}, Data: {data[original_index]}")

    # Expected behavior: anomalies (indices 100, 101, 102, 103) should have higher scores (closer to 1)
