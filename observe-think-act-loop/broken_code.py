def calculate_average(numbers):
    if not numbers:
        return 0
    total = sum(number)
    return total / len(numers)

if __name__ == "__main__":
    print(calculate_average([10, 20, 30]))
    print(calculate_average([]))