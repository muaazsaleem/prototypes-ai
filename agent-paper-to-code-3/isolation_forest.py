
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

def _c(n):
    """
    Calculates the average path length of an unsuccessful search in a Binary Search Tree.
    Used for normalization in anomaly score calculation.
    Equation 1 from the paper.
    """
    if n <= 1:
        return 0.0
    # Euler's constant is approximately 0.5772156649
    return 2 * (math.log(n - 1) + 0.5772156649) - (2 * (n - 1) / n)

def _iTree(X, current_height, height_limit):
    """
    Builds a single Isolation Tree (iTree) recursively.
    Algorithm 2 from the paper.

    X: list of lists (or tuples), input data.
    """
    num_instances = len(X)
    if num_instances == 0:
        return None

    if current_height >= height_limit or num_instances <= 1:
        return ExNode(num_instances)
    else:
        # Check if all data in X have the same values (condition iii)
        first_instance = X[0]
        all_same = True
        for instance in X:
            if instance != first_instance:
                all_same = False
                break
        if all_same:
            return ExNode(num_instances)

        # Randomly select an attribute (column index)
        num_attributes = len(X[0])
        q = random.randint(0, num_attributes - 1)

        # Find min and max values for attribute q
        min_val = X[0][q]
        max_val = X[0][q]
        for instance in X:
            if instance[q] < min_val:
                min_val = instance[q]
            if instance[q] > max_val:
                max_val = instance[q]

        # Handle the case where min_val and max_val are the same
        if min_val == max_val:
            return ExNode(num_instances) # Cannot split, all values are the same for this attribute

        # Randomly select a split point p between the min and max values of attribute q
        p = random.uniform(min_val, max_val)

        # Filter data points for left and right branches
        X_left = []
        X_right = []
        for instance in X:
            if instance[q] < p:
                X_left.append(instance)
            else:
                X_right.append(instance)

        # Ensure that both X_left and X_right are not empty.
        # If one is empty, it means the split didn't effectively divide the data,
        # so we terminate this branch to prevent infinite recursion or an imbalance.
        if not X_left or not X_right:
            return ExNode(num_instances)

        left_child = _iTree(X_left, current_height + 1, height_limit)
        right_child = _iTree(X_right, current_height + 1, height_limit)

        # If for some reason a child is None (e.g. empty X passed to _iTree),
        # it means no further split was possible, so we convert this internal node
        # to an external node for the current partition (this scenario should be handled by the empty check above).
        # Adding an explicit check for None children to be safe, though ideally the checks above prevent this.
        if left_child is None or right_child is None:
            return ExNode(num_instances)

        return InNode(left_child, right_child, q, p)

def _path_length(x, tree, current_height):
    """
    Calculates the path length for a single instance x in a given iTree.
    Algorithm 3 from the paper.
    """
    if isinstance(tree, ExNode):
        # If the external node contains more than one instance,
        # adjust the path length using c(size)
        return current_height + _c(tree.size)
    else: # Internal Node
        # Access the attribute value from the instance x
        if x[tree.split_attribute] < tree.split_value:
            return _path_length(x, tree.left, current_height + 1)
        else:
            return _path_length(x, tree.right, current_height + 1)


class IsolationForest:
    """
    Implements the Isolation Forest algorithm.
    Algorithm 1 from the paper.
    """
    def __init__(self, n_estimators=100, max_samples=256, random_state=None):
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.random_state = random_state
        self.i_trees = []
        self.height_limit = 0

    def fit(self, X):
        """
        Fits the Isolation Forest to the training data.
        X: list of lists (or tuples), input data.
        """
        if self.random_state is not None:
            random.seed(self.random_state)

        # Automatically set height limit l = ceiling(log2(max_samples))
        # The paper specifies l = ceiling(log2(psi)) which is max_samples
        self.height_limit = math.ceil(math.log2(self.max_samples))

        self.i_trees = []
        for _ in range(self.n_estimators):
            # Sample a sub-sample X' from X
            # Ensure max_samples does not exceed the number of available instances
            num_total_instances = len(X)
            num_samples_to_take = min(self.max_samples, num_total_instances)

            # Randomly select indices for the sub-sample
            # If num_total_instances is 0, random.sample will raise an error. Guard against this.
            if num_total_instances == 0:
                continue
            sampled_indices = random.sample(range(num_total_instances), num_samples_to_take)
            X_sample = [X[i] for i in sampled_indices]

            tree = _iTree(X_sample, 0, self.height_limit)
            # Only add valid trees (not None due to empty samples, though we filter that in _iTree)
            if tree is not None:
                self.i_trees.append(tree)
        return self

    def _average_path_length(self, X):
        """
        Calculates the average path length for each instance in X across all iTrees.
        X: list of lists (or tuples), input data.
        """
        path_lengths = [0.0] * len(X)
        if not self.i_trees: # Handle case where no trees were built
            return path_lengths

        for x_idx, x in enumerate(X):
            h_x_sum = 0
            for tree in self.i_trees:
                h_x_sum += _path_length(x, tree, 0)
            path_lengths[x_idx] = h_x_sum / len(self.i_trees)
        return path_lengths

    def decision_function(self, X):
        """
        Computes the anomaly scores for the given instances.
        X: list of lists (or tuples), test data.
        Returns: list of anomaly scores.
        """
        if not self.i_trees:
            # If no trees were fitted, return a default score (e.g., 0.5 as neutral)
            return [0.5] * len(X)

        # Calculate average path lengths E(h(x))
        avg_path_lengths = self._average_path_length(X)

        # Calculate anomaly scores s(x, n) using Equation 2
        # n is the sub-sampling size (max_samples) used during training
        # c(n) is the normalization factor based on the sub-sampling size
        c_val = _c(self.max_samples)

        anomaly_scores = []
        if c_val == 0: # Avoid division by zero if max_samples is 1
            # If c_val is 0, it means max_samples was 1, so all path lengths will be 0.
            # In this case, E(h(x))/c(n) would be undefined or lead to issues.
            # According to the paper, s -> 0.5 when E(h(x)) -> c(n).
            # If max_samples = 1, then _c(1) = 0. E(h(x)) would also be 0 for any point.
            # So 0/0 is problematic. Returning 0.5 is a reasonable neutral score.
            return [0.5] * len(X)

        for apl in avg_path_lengths:
            # Ensure apl / c_val doesn't lead to math domain error if apl is negative or c_val is negative.
            # Path lengths are always non-negative.
            score = 2 ** (-apl / c_val)
            anomaly_scores.append(score)

        return anomaly_scores

if __name__ == '__main__':
    # Test Case: Generate synthetic data
    # Normal data: cluster around (0,0)
    num_normal = 200
    normal_data = []
    for _ in range(num_normal):
        normal_data.append([random.gauss(0, 0.5), random.gauss(0, 0.5)])

    # Anomaly data: far from (0,0)
    num_anomalies = 10
    anomaly_data = []
    for _ in range(num_anomalies):
        anomaly_data.append([random.gauss(5, 1), random.gauss(5, 1)])

    # Combine data
    X_combined = normal_data + anomaly_data
    # Shuffle to mix normal and anomaly points
    random.shuffle(X_combined)

    print(f"Generated {len(normal_data)} normal points and {len(anomaly_data)} anomaly points.")

    # Initialize and train Isolation Forest
    # Use a fixed random_state for reproducibility
    # max_samples should be chosen carefully; 256 is the default in the paper
    iforest = IsolationForest(n_estimators=100, max_samples=256, random_state=42)
    iforest.fit(X_combined)

    print("Isolation Forest fitted.")

    # Get anomaly scores for all points
    scores = iforest.decision_function(X_combined)

    # Print scores, indicating which were originally normal/anomaly
    # To do this correctly, we need to preserve the original labels or indices
    # Let's re-run decision_function on original normal and anomaly sets to see separation
    normal_scores = iforest.decision_function(normal_data)
    anomaly_scores = iforest.decision_function(anomaly_data)

    print("\n--- Anomaly Scores for Normal Data ---")
    # Print a sample of normal scores
    for i, score in enumerate(normal_scores[:10]):
        print(f"Normal point {i}: {score:.4f}")
    print(f"... (and {len(normal_scores) - 10} more)")
    print(f"Average normal score: {sum(normal_scores) / len(normal_scores):.4f}")
    print(f"Min normal score: {min(normal_scores):.4f}")
    print(f"Max normal score: {max(normal_scores):.4f}")

    print("\n--- Anomaly Scores for Anomaly Data ---")
    for i, score in enumerate(anomaly_scores):
        print(f"Anomaly point {i}: {score:.4f}")
    print(f"Average anomaly score: {sum(anomaly_scores) / len(anomaly_scores):.4f}")
    print(f"Min anomaly score: {min(anomaly_scores):.4f}")
    print(f"Max anomaly score: {max(anomaly_scores):.4f}")

    # Basic verification: Anomalies should generally have higher scores than normal points
    # Note: With randomness, a perfect separation isn't guaranteed in a small test.
    avg_normal = sum(normal_scores) / len(normal_scores)
    avg_anomaly = sum(anomaly_scores) / len(anomaly_scores)

    if avg_anomaly > avg_normal:
        print("\nVerification: Average anomaly score is HIGHER than average normal score. (GOOD)")
    else:
        print("\nVerification: Average anomaly score is NOT higher than average normal score. (CHECK)")

    # Check if any anomaly score is close to 1 and normal scores are closer to 0.5 or lower
    highest_anomaly_score = max(anomaly_scores)
    lowest_normal_score = min(normal_scores)

    if highest_anomaly_score > 0.7 and lowest_normal_score < 0.6:
        print("Scores show good separation. (GOOD)")
    else:
        print("Scores show less separation than ideal. (CHECK)")


