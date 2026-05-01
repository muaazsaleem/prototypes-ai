import numpy as np
from collections import defaultdict, deque
import random

class Word2VecBase:
    """
    Base class for Word2Vec models (CBOW and Skip-gram).
    Handles vocabulary creation, word-to-index mapping, and embedding initialization.
    """
    def __init__(self, corpus, embedding_dim, window_size, min_count=1):
        self.corpus = corpus
        self.embedding_dim = embedding_dim
        self.window_size = window_size
        self.min_count = min_count
        self.word_to_idx = {}
        self.idx_to_word = {}
        self.vocabulary_size = 0
        self.word_counts = defaultdict(int)
        self.init_vocabulary()
        self.init_embeddings()

    def init_vocabulary(self):
        """
        Builds the vocabulary from the corpus, mapping words to unique indices.
        Filters words based on min_count.
        """
        for sentence in self.corpus:
            for word in sentence:
                self.word_counts[word] += 1

        idx = 0
        for word, count in self.word_counts.items():
            if count >= self.min_count:
                self.word_to_idx[word] = idx
                self.idx_to_word[idx] = word
                idx += 1
        self.vocabulary_size = len(self.word_to_idx)
        print(f"Vocabulary size: {self.vocabulary_size}")

    def init_embeddings(self):
        """
        Initializes input and output word embeddings with random values.
        Input embeddings (W) are for the words themselves.
        Output embeddings (W_out) are for the context/target predictions.
        """
        # Input word embeddings (weights from input to projection layer)
        self.W = np.random.uniform(-0.8, 0.8, (self.vocabulary_size, self.embedding_dim))
        # Output word embeddings (weights from projection to output layer)
        self.W_out = np.random.uniform(-0.8, 0.8, (self.vocabulary_size, self.embedding_dim))

    def one_hot_encode(self, word_idx):
        """
        Creates a one-hot encoding vector for a given word index.
        """
        one_hot = np.zeros(self.vocabulary_size)
        one_hot[word_idx] = 1
        return one_hot

    def softmax(self, x):
        """
        Computes the softmax function.
        """
        e_x = np.exp(x - np.max(x)) # Subtract max for numerical stability
        return e_x / e_x.sum(axis=0)

    def generate_training_data(self):
        """
        Abstract method to be implemented by subclasses for generating
        (input, target) pairs.
        """
        raise NotImplementedError

    def train(self, epochs, learning_rate):
        """
        Abstract method to be implemented by subclasses for training.
        """
        raise NotImplementedError

class CBOW(Word2VecBase):
    """
    Continuous Bag-of-Words (CBOW) model implementation.
    Predicts the current word based on its surrounding context words.
    """
    def __init__(self, corpus, embedding_dim, window_size, min_count=1):
        super().__init__(corpus, embedding_dim, window_size, min_count)

    def generate_training_data(self):
        """
        Generates (context_word_indices, target_word_idx) pairs for CBOW.
        Context words are averaged to predict the target word.
        """
        training_data = []
        for sentence in self.corpus:
            sentence_indices = [self.word_to_idx[word] for word in sentence if word in self.word_to_idx]
            for i, target_word_idx in enumerate(sentence_indices):
                context_word_indices = []
                for j in range(max(0, i - self.window_size), min(len(sentence_indices), i + self.window_size + 1)):
                    if i != j: # Exclude the target word itself
                        context_word_indices.append(sentence_indices[j])
                if context_word_indices: # Only add if there's a context
                    training_data.append((context_word_indices, target_word_idx))
        return training_data

    def train(self, epochs=10, learning_rate=0.01):
        """
        Trains the CBOW model using stochastic gradient descent.
        """
        training_data = self.generate_training_data()
        print(f"Training CBOW model with {len(training_data)} samples for {epochs} epochs...")

        for epoch in range(epochs):
            total_loss = 0
            for context_indices, target_idx in training_data:
                # 1. Input Layer: Average of context word embeddings
                h = np.mean([self.W[idx] for idx in context_indices], axis=0)

                # 2. Output Layer: Calculate scores for all words in vocabulary
                u = np.dot(h, self.W_out.T)

                # 3. Softmax to get probabilities
                y_pred = self.softmax(u)

                # 4. Calculate error (e.g., cross-entropy loss)
                # One-hot encode the true target word
                y_true = self.one_hot_encode(target_idx)
                loss = -np.sum(y_true * np.log(y_pred + 1e-9)) # Add epsilon for numerical stability
                total_loss += loss

                # 5. Backpropagation
                # Error at the output layer
                e = y_pred - y_true

                # Gradient for W_out (output embeddings)
                # dL/dW_out = h_projection_layer * error_output_layer
                dW_out = np.outer(e, h) # (V, D)

                # Error propagated back to the projection layer
                # dL/dh = W_out_transpose * error_output_layer
                eh = np.dot(e, self.W_out) # (D,)

                # Gradient for W (input embeddings)
                # Since h is the average of context word embeddings,
                # the error eh is distributed equally among the context words.
                dW = np.zeros_like(self.W)
                for context_word_idx in context_indices:
                    dW[context_word_idx] += eh / len(context_indices)

                # Update weights
                self.W_out -= learning_rate * dW_out
                self.W -= learning_rate * dW

            print(f"Epoch {epoch + 1}/{epochs}, Loss: {total_loss:.4f}")

        print("CBOW training complete.")

class SkipGram(Word2VecBase):
    """
    Skip-gram model implementation.
    Predicts context words based on a given target word.
    """
    def __init__(self, corpus, embedding_dim, window_size, min_count=1):
        super().__init__(corpus, embedding_dim, window_size, min_count)

    def generate_training_data(self):
        """
        Generates (target_word_idx, context_word_idx) pairs for Skip-gram.
        """
        training_data = []
        for sentence in self.corpus:
            sentence_indices = [self.word_to_idx[word] for word in sentence if word in self.word_to_idx]
            for i, target_word_idx in enumerate(sentence_indices):
                for j in range(max(0, i - self.window_size), min(len(sentence_indices), i + self.window_size + 1)):
                    if i != j: # Exclude the target word itself
                        context_word_idx = sentence_indices[j]
                        training_data.append((target_word_idx, context_word_idx))
        return training_data

    def train(self, epochs=10, learning_rate=0.01):
        """
        Trains the Skip-gram model using stochastic gradient descent.
        """
        training_data = self.generate_training_data()
        print(f"Training Skip-gram model with {len(training_data)} samples for {epochs} epochs...")

        for epoch in range(epochs):
            total_loss = 0
            for target_idx, context_idx in training_data:
                # 1. Input Layer: Get embedding for the target word
                h = self.W[target_idx]

                # 2. Output Layer: Calculate scores for all words in vocabulary
                u = np.dot(h, self.W_out.T)

                # 3. Softmax to get probabilities
                y_pred = self.softmax(u)

                # 4. Calculate error
                y_true = self.one_hot_encode(context_idx)
                loss = -np.sum(y_true * np.log(y_pred + 1e-9))
                total_loss += loss

                # 5. Backpropagation
                e = y_pred - y_true

                # Gradient for W_out (output embeddings)
                # dL/dW_out = h_projection_layer * error_output_layer
                dW_out = np.outer(e, h) # (V, D)

                # Error propagated back to the projection layer
                # dL/dh = W_out_transpose * error_output_layer
                eh = np.dot(e, self.W_out) # (D,)

                # Gradient for W (input embeddings)
                # Only the target word's embedding is updated
                dW = np.zeros_like(self.W)
                dW[target_idx] = eh

                # Update weights
                self.W_out -= learning_rate * dW_out
                self.W -= learning_rate * dW

            print(f"Epoch {epoch + 1}/{epochs}, Loss: {total_loss:.4f}")

        print("Skip-gram training complete.")

if __name__ == "__main__":
    # Demo of CBOW and Skip-gram models

    # Sample corpus
    corpus = [
        ["natural", "language", "processing", "is", "a", "field", "of", "artificial", "intelligence"],
        ["word", "embeddings", "are", "used", "in", "nlp", "tasks"],
        ["cbow", "and", "skip-gram", "are", "two", "popular", "word2vec", "models"],
        ["deep", "learning", "has", "revolutionized", "nlp"]
    ]

    embedding_dim = 10 # Dimension of word vectors
    window_size = 2    # Context window size
    epochs = 50        # Number of training epochs
    learning_rate = 0.01 # Learning rate

    print("--- Training CBOW Model ---")
    cbow_model = CBOW(corpus, embedding_dim, window_size, min_count=1)
    cbow_model.train(epochs=epochs, learning_rate=learning_rate)

    print("\n--- CBOW Embeddings (first 5 words) ---")
    for i in range(min(5, cbow_model.vocabulary_size)):
        word = cbow_model.idx_to_word[i]
        embedding = cbow_model.W[i]
        print(f"Word: {word}, Embedding: {embedding[:5]}...") # Print first 5 dimensions

    print("\n--- Training Skip-gram Model ---")
    skipgram_model = SkipGram(corpus, embedding_dim, window_size, min_count=1)
    skipgram_model.train(epochs=epochs, learning_rate=learning_rate)

    print("\n--- Skip-gram Embeddings (first 5 words) ---")
    for i in range(min(5, skipgram_model.vocabulary_size)):
        word = skipgram_model.idx_to_word[i]
        embedding = skipgram_model.W[i]
        print(f"Word: {word}, Embedding: {embedding[:5]}...") # Print first 5 dimensions

    # Example of finding similar words (very basic cosine similarity)
    def find_similar_words(word, model, top_n=3):
        if word not in model.word_to_idx:
            return f"'{word}' not in vocabulary."
        word_idx = model.word_to_idx[word]
        word_embedding = model.W[word_idx]

        similarities = {}
        for i, other_word in model.idx_to_word.items():
            if other_word == word:
                continue
            other_embedding = model.W[i]
            # Cosine similarity
            similarity = np.dot(word_embedding, other_embedding) / (
                np.linalg.norm(word_embedding) * np.linalg.norm(other_embedding) + 1e-9
            )
            similarities[other_word] = similarity

        sorted_similarities = sorted(similarities.items(), key=lambda item: item[1], reverse=True)
        return sorted_similarities[:top_n]

    print("\n--- Similar words using CBOW embeddings ---")
    print(f"Words similar to 'nlp': {find_similar_words('nlp', cbow_model)}")
    print(f"Words similar to 'word': {find_similar_words('word', cbow_model)}")

    print("\n--- Similar words using Skip-gram embeddings ---")
    print(f"Words similar to 'nlp': {find_similar_words('nlp', skipgram_model)}")
    print(f"Words similar to 'word': {find_similar_words('word', skipgram_model)}")

    # Note on optimizations:
    # The paper mentions Hierarchical Softmax and Negative Sampling for efficiency
    # with large vocabularies. These are not implemented here for simplicity
    # and to keep the code self-contained without external libraries.
    # In a production setting, these optimizations are crucial for performance.
    # Hierarchical Softmax replaces the full softmax calculation with a binary tree
    # structure, reducing complexity from V to log(V).
    # Negative Sampling replaces the full softmax with a binary classification task
    # for the true target and a few randomly sampled "negative" words.