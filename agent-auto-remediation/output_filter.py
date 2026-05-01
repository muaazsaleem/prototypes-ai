from agent import RemediationProposal

# Services that must never be touched by automated remediation.
# Any action targeting these is blocked regardless of risk score —
# they require human review because the blast radius or revenue impact is too high.
PROTECTED_RESOURCES = {
    "payment-service",
    "billing-service",
    "production-db-primary",
    "fraud-detection-service",
    "auth-service",
}


class OutputFilter:
    """Blocks remediation actions that target protected infrastructure."""

    def check(self, proposal: RemediationProposal) -> tuple[bool, str]:
        """Returns (is_safe, reason) — False blocks the action regardless of risk score.

        Checks both the target_service field and all string parameter values because
        the agent sometimes encodes the service name inside a parameter rather than the
        explicit target_service field.
        """
        action = proposal.proposed_action

        # Check the explicit target_service field first
        target = action.get("target_service", "")
        if target in PROTECTED_RESOURCES:
            return False, f"'{target}' is in the protected resource list"

        # Also scan all parameter values — the agent might name the service
        # in a parameter (e.g. restart_service(service="payment-service"))
        for param_value in action.get("parameters", {}).values():
            if isinstance(param_value, str) and param_value in PROTECTED_RESOURCES:
                return (
                    False,
                    f"Action parameter references protected resource '{param_value}'",
                )

        return True, "Action targets an in-scope resource"
