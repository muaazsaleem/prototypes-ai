import argparse
import sys

from agent import CodingAgent


def main():
    """Parses command-line arguments and executes the CodingAgent loop.

    Handles input task, repository path, and iteration budget.
    Exits with code 0 on success (all tests pass) or code 1 on failure/escalation.
    """
    parser = argparse.ArgumentParser(
        description="Coding Agent — ReAct + Reflexion loop over a codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py 'Fix all failing tests' --repo ./demo\n"
            "  python main.py 'Add input validation to utils.py' --repo ./myproject --max-iter 3\n"
        ),
    )
    # the task description is the primary input
    parser.add_argument(
        "task", help="Natural language description of what the agent should do"
    )
    # defaults to current directory if no path provided
    parser.add_argument(
        "--repo",
        default=".",
        metavar="PATH",
        help="Path to the repository root (default: current directory)",
    )
    # iteration budget prevents infinite loops and excessive API costs
    parser.add_argument(
        "--max-iter",
        type=int,
        default=5,
        metavar="N",
        help="Maximum ReAct + Reflexion iterations before escalating (default: 5)",
    )
    args = parser.parse_args()

    # instantiate and run the agent with the provided configuration
    agent = CodingAgent(repo_path=args.repo, max_iterations=args.max_iter)
    success = agent.run(args.task)

    # propagate success status as process exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
