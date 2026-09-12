# Deploying Ixia-C traffic generators

Ansible roles that turn a bare Linux host into an OTG traffic generator that
`otg-mcp` can drive.

All targets are remote, reached over SSH. Ansible runs in a container, so the
only local requirement is Docker. **Ansible is not a dependency of the `otg_mcp`
package** — it is pinned in `requirements.txt` here and installed only into that
container.

## Requirements

Targets must be:

- **Debian or Ubuntu**, reachable over SSH, with a sudo-capable account. The
  playbook stops with a clear message on other distributions.
- **x86_64 or arm64**, with Internet access (it clones Ixia-C, pulls images from
  ghcr.io, and downloads `otgen`).
- Fitted with **at least one spare NIC**. The interface carrying the host's
  default route is refused, so a single-NIC host cannot be used.

The control node needs only Docker. Everything else runs in the container.

## Quick start

```bash
cp inventory/hosts.yml.example inventory/hosts.yml   # edit: host, interface, driver
docker compose run --rm ansible deploy
```

`inventory/hosts.yml` is gitignored, so your hosts stay out of the repo.

| Verb | What it does |
|---|---|
| `deploy` | Prerequisites, DPDK if requested, containers, verification |
| `verify` | Health check of an existing deployment. Read-only: unlike `deploy` it does not transmit, because applying a flow replaces whatever config is loaded on the generator |
| `check` | Dry run (`--check --diff`) |
| `dpdk` | Bind a host's NICs to DPDK only |
| `revert-dpdk` | Return DPDK-bound NICs to their kernel driver |
| `ping` | Confirm SSH reachability |
| `facts` | Dump host facts (useful for finding interface names) |
| `lint` | `ansible-lint` over the roles |
| `shell` | Interactive shell in the control-node container |

Extra arguments pass straight through:

```bash
docker compose run --rm ansible deploy --limit lab-1.example.com
docker compose run --rm ansible deploy -vv
```

To deploy a host with no inventory entry, pass an inventory on the command line
(note the trailing comma) along with its settings:

```bash
docker compose run --rm ansible ansible-playbook site.yml \
  -i lab-9.example.com, -e otg_target=lab-9.example.com \
  -e otg_driver=af_packet -e '{"otg_interfaces": ["enp1s0"]}'
```

### Environment

| Variable | Why |
|---|---|
| `BECOME_PASS` | Sudo password. Unset means you are prompted. |
| `NO_BECOME_PROMPT=1` | Targets have passwordless sudo. |
| `OTG_DNS` | DNS server that resolves your lab names. Containers do not inherit the host resolver, so `.local` and internal zones fail without it. |
| `ANSIBLE_REMOTE_USER` | SSH user. Defaults to your local `$USER`. |
| `SSH_DIR` | SSH keys to mount. Defaults to `~/.ssh`. |

## Inventory

```yaml
all:
  children:
    traffic_generators:
      hosts:
        lab-1.example.com:          # must be the address otg-mcp will use
          otg_mode: one-arm         # one-arm | two-arm | three-arm
          otg_driver: af_packet     # af_packet | dpdk
          otg_interfaces: [enp1s0]  # explicit, never auto-detected
```

The inventory hostname *is* the target's address: an `otg-mcp` target key is its
address, so use the name (or IP) that `otg-mcp` will connect to.

Interfaces are declared, not detected. The shell script this replaced guessed by
pattern, and on one lab host it chose `eth1`/`eth2`/`eth3` — interfaces that did
not exist there — leaving a traffic engine bound to nothing while every check
still passed. The roles refuse an interface carrying the host's default route,
refuse to hand a NIC holding an IP address to DPDK, and warn about one with no
carrier.

## af_packet vs DPDK

`af_packet` is the kernel socket path: any NIC, no host changes, and it tops out
around **3 Gbps** because the send path is CPU-bound. `dpdk` polls in userspace
and reaches **line rate**. Measured transmit on the same Intel X540 port, read
from the NIC's own counters: **2.86 Gbps** with af_packet against **9.65 Gbps**
with DPDK (payload bytes; ~9.8 Gbps once preamble and inter-frame gap are
counted).

DPDK needs only the interface name; the role resolves its PCI address and
records the mapping on the target, which is what lets a re-run or a revert work
after the NIC has left the kernel:

```yaml
        lab-2.example.com:
          otg_driver: dpdk
          otg_interfaces: [enp11s0f0]
          otg_cpu_cores: "2,3,4,5"        # dedicated cores, avoid core 0
          otg_link_speed: speed_10_gbps   # required: DPDK reports no line speed
```

Keep `otg_link_autoneg` at its default of `true` on copper. 10GBASE-T requires
autonegotiation, and forcing a speed with it off leaves the port link **down**
while the engine still counts frames — so a dead link looks like a successful
transmit. Verification reads the NIC's own counters and warns when a port is
down, for exactly this reason.

A DPDK-bound NIC **disappears from the kernel** — no `ip addr`, no `ethtool`, no
af_packet. That is why `revert-dpdk` exists. The binding does not survive a
reboot (hugepages and `allow_unsafe_interrupts` do), so re-run `dpdk` after one.

Preflight checks refuse to proceed unless IOMMU is enabled and the target device
is **alone in its IOMMU group** — vfio-pci claims the whole group, so binding a
device that shares one would detach the others from their drivers.

On a platform whose IOMMU lacks interrupt remapping (common on AMD), VFIO will
not attach the group at all, and the only workaround weakens host isolation: a
userspace driver could inject MSIs at the host. It is therefore opt-in per host:

```yaml
          dpdk_allow_unsafe_interrupts: true
```

## Known host-level traps

Two problems found on real hardware that the roles now detect and explain rather
than fail obscurely:

- **Docker's apt repo lags new releases.** On Ubuntu 26.04 `docker-ce` has no
  installation candidate. The role probes the repo and falls back to the
  distribution's `docker.io`. It cannot simply use `geerlingguy.docker`, whose
  `docker_obsolete_packages` *removes* `docker.io` before installing `docker-ce`,
  which would uninstall the only Docker that works there. That role is used on
  releases Docker does publish for.
- **Two Docker daemons.** A snap `dockerd` plus the distribution's compete for
  `/var/run/docker.sock`. Containers land in one daemon while the other's keep
  holding 5555/5600/8443, so the stack crash-loops forever *while the API
  answers from the stale deployment*. Verification asserts no container is
  restarting, precisely because a stale process made an unhealthy host look fine.

`sudo-rs` (default on Ubuntu 25.10+) does not flush its password prompt before
reading stdin, so Ansible's become times out. The `sudo_compat` role detects it
and uses classic sudo at `/usr/bin/sudo.ws`.

## Other variables

Defaults live in `group_vars/all.yml`; per-role defaults in `roles/*/defaults/`.

| Variable | Purpose |
|---|---|
| `otg_api_port` | Controller API port (8443) |
| `otg_repo_url`, `otg_repo_dir`, `otg_ixia_commit`, `otg_update_repo` | Which Ixia-C to deploy, and whether to track the branch tip instead of the pinned commit |
| `otg_controller_version`, `otg_traffic_engine_version`, `otg_aur_version` | Container image tags |
| `otg_run_traffic_verify` | Transmit during verification (on for `deploy`, off for `verify`) |
| `otg_compose_project` | Compose project name used to scope container checks |
| `dpdk_hugepages` | 2MB pages to reserve (2048 = 4GB) |
| `dpdk_skip_group_isolation_check` | Override the IOMMU-group check. Only after confirming every other device in the group is unused |
| `dpdk_revert_hugepages`, `dpdk_revert_unsafe_interrupts` | Whether `revert-dpdk` also undoes those host-wide changes (both off, since another deployment may need them) |
| `docker_add_user_to_group` | Add the login user to the `docker` group (root-equivalent; on by default) |
| `verify_frame_count`, `verify_frame_size`, `verify_frame_rate` | The verification flow |

## What the roles write on the target

`~/ixia-c` (cloned, and hard-reset on each run), its `deployments/docker-compose.yml`
(rendered), `~/.local/bin/otgen`, `/tmp/otg-mcp-verify.json`, and — for DPDK only —
`/etc/otg-mcp-dpdk-bindings.json`, `/etc/sysctl.d/99-dpdk-hugepages.conf` and
`/etc/modprobe.d/vfio-dpdk.conf`.

SSH host-key checking is disabled (`ansible.cfg`), matching this project's
existing stance that lab gear uses self-signed certs and changes often.

## After deploying

Add the target to your `otg-mcp` config, keyed by address:

```json
{"targets": {"lab-1.example.com:8443": {"ports": {"p1": {"location": "localhost:5555", "name": "p1"}}}}}
```

`frames_rx: 0` in verification output is expected for one-arm with nothing
looping back — transmitted frames have nowhere to return from.

## Roles

| Role | Responsibility |
|---|---|
| `sudo_compat` | Works around sudo-rs breaking password-authenticated become |
| `docker` | Installs Docker, choosing upstream or distribution packages |
| `net_utils` | Network diagnostic tooling |
| `otgen` | Installs `otgen` for manual use, resolving the latest release |
| `dpdk` | Hugepages, vfio-pci binding, and the revert path |
| `ixia_c` | Repository, compose file, containers |
| `verify` | API, container health, DPDK binding, and a real traffic flow |

Verification drives the controller's REST API rather than `otgen`, because a
pinned `otgen` breaks against a newer controller (it cannot unmarshal
`tx_rate_bps`) and emits no `layer1` section, which a DPDK port requires.

## Running without the container

```bash
pip install -r requirements.txt
ansible-galaxy install -r requirements.yml
ansible-playbook site.yml --ask-become-pass
```
