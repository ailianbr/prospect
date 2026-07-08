#!/usr/bin/env python3
"""Generate the dev/test PocketBase schema (pb_schema.dev.json).

The repo ships two schemas that disagree with the handler code (see below), so neither
seeds a PB the whole test suite can run against. This produces a single dev/test fixture:

  - core collections from pb_schema.json (monk_client_lists with `client` as TEXT — the
    documented contract the core tests rely on; the merged file makes it a relation, which
    can't hold ids like "mxf");
  - the chatwoot collections from pb_schema_new.json (instances, services, instance_services,
    service_secrets, common_service_config, conectai_instance_config + the merged
    monk_channel_configs), with:
      * `monk_channel_configs.handler` enum extended with "chat" — the handler queries
        handler="chat" (handlers/chatwoot/handler.py) but the merged enum only lists "chatwoot";
      * API rules stripped to null (dev/test auths as superuser, which bypasses rules, and the
        merged rules reference collections we don't import).

This is a TEST FIXTURE reconstructed from the code's expectations — NOT the deployed schema.
Regenerate when the source schemas change:

    python tools/dev/gen_dev_schema.py services/pocketbase/pb_schema.json \
        services/pocketbase/pb_schema_new.json > services/pocketbase/pb_schema.dev.json
"""

import json
import sys

CHATWOOT = ['instances', 'services', 'instance_services', 'service_secrets',
            'common_service_config', 'conectai_instance_config']


def build(core_path: str, merged_path: str) -> list:
    core = {c['name']: c for c in json.load(open(core_path))}
    merged = {c['name']: c for c in json.load(open(merged_path))}

    keep_ids = {core['monk_client_lists']['id'], core['monk_lists']['id']} | {
        merged[n]['id'] for n in CHATWOOT + ['monk_channel_configs']
    }

    def strip_rules(c):
        for r in ('listRule', 'viewRule', 'createRule', 'updateRule', 'deleteRule'):
            c[r] = None
        return c

    out = [core['monk_client_lists'], core['monk_lists']]
    for n in CHATWOOT:
        c = strip_rules(json.loads(json.dumps(merged[n])))
        # drop relation fields pointing at collections we don't import (e.g. ...tool -> tools)
        c['fields'] = [f for f in c['fields']
                       if not (f.get('type') == 'relation' and f.get('collectionId') not in keep_ids)]
        out.append(c)

    mcc = strip_rules(json.loads(json.dumps(merged['monk_channel_configs'])))
    for f in mcc['fields']:
        if f['name'] == 'handler' and f.get('type') == 'select' and 'chat' not in f['values']:
            f['values'].append('chat')
    out.append(mcc)
    return out


if __name__ == '__main__':
    core_path = sys.argv[1] if len(sys.argv) > 1 else 'services/pocketbase/pb_schema.json'
    merged_path = sys.argv[2] if len(sys.argv) > 2 else 'services/pocketbase/pb_schema_new.json'
    json.dump(build(core_path, merged_path), sys.stdout, indent=2)
    sys.stdout.write('\n')
