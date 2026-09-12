#!/bin/sh
# Maps short verbs onto playbook invocations so callers do not have to remember
# ansible-playbook syntax. Extra arguments are passed straight through, so
# things like --limit, --check and -vvv still work:
#   docker compose run --rm ansible deploy --limit lab-1.example.com
set -e

verb="${1:-help}"
[ $# -gt 0 ] && shift

# Ask for the sudo password unless the caller supplied one or the targets have
# passwordless sudo. BECOME_PASS is read by ansible.cfg.
become_args=""
if [ -z "${BECOME_PASS:-}" ] && [ "${NO_BECOME_PROMPT:-}" != "1" ]; then
    become_args="--ask-become-pass"
fi

case "$verb" in
    deploy)
        exec ansible-playbook site.yml $become_args "$@"
        ;;
    dpdk)
        exec ansible-playbook dpdk.yml $become_args "$@"
        ;;
    revert-dpdk)
        exec ansible-playbook dpdk-revert.yml $become_args "$@"
        ;;
    verify)
        # Genuinely read-only. The traffic check is disabled here because applying
        # a flow replaces whatever configuration is loaded on the generator,
        # which would disrupt a colleague's experiment. Add
        # -e otg_run_traffic_verify=true to include it.
        exec ansible-playbook site.yml --tags verify \
            -e otg_run_traffic_verify=false "$@"
        ;;
    check)
        exec ansible-playbook site.yml --check --diff $become_args "$@"
        ;;
    facts)
        exec ansible traffic_generators -m setup "$@"
        ;;
    ping)
        exec ansible traffic_generators -m ping "$@"
        ;;
    lint)
        exec ansible-lint "$@"
        ;;
    shell|sh)
        exec /bin/sh
        ;;
    help|-h|--help)
        cat <<'USAGE'
Ixia-C deployment control node.

  docker compose run --rm ansible <verb> [extra ansible args]

Verbs:
  deploy        Full deploy: prerequisites, DPDK if requested, containers, verify
  verify        Read-only health check of an existing deployment
  check         Dry run (--check --diff), changes nothing
  dpdk          Bind a host's NICs to DPDK only
  revert-dpdk   Return DPDK-bound NICs to their kernel driver
  ping          Confirm SSH reachability of every target
  facts         Dump gathered facts (useful for finding interface names)
  lint          Run ansible-lint over the roles
  shell         Interactive shell in this container

Targets come from inventory/hosts.yml. Limit to one host with
--limit <inventory_hostname>.

Set BECOME_PASS to avoid the sudo prompt, or NO_BECOME_PROMPT=1 when targets
have passwordless sudo.
USAGE
        ;;
    *)
        # Anything else is treated as a command, so ansible-playbook, ansible,
        # ansible-galaxy etc. remain directly available.
        exec "$verb" "$@"
        ;;
esac
