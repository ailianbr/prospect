# Changelog

## [0.8.0](https://github.com/ailianbr/prospect/compare/monk-api-v0.7.0...monk-api-v0.8.0) (2026-07-08)


### Features

* **api:** report environment in /health ([6c44687](https://github.com/ailianbr/prospect/commit/6c446876405a33e9daab710e33a5185c1bfd71ce))
* **api:** report environment in /health ([ca5493c](https://github.com/ailianbr/prospect/commit/ca5493c91b94e48ac7b35993b2a15d2d01f537ff))

## [0.7.0](https://github.com/ailianbr/prospect/compare/monk-api-v0.6.0...monk-api-v0.7.0) (2026-07-08)


### Features

* **api:** /health endpoint + ci: gate prod deploy on live staging ([bfd0cea](https://github.com/ailianbr/prospect/commit/bfd0cea38330f337ac94e9324e481fb45fd62fe8))
* **api:** add unauthenticated /health endpoint ([4cabb7d](https://github.com/ailianbr/prospect/commit/4cabb7dad2afa172887db1a75653ec139c6a4655))

## [0.6.0](https://github.com/ailianbr/prospect/compare/monk-api-v0.5.0...monk-api-v0.6.0) (2026-07-08)


### Features

* **api:** add subscriber CRUD endpoints ([891caae](https://github.com/ailianbr/prospect/commit/891caae964d471ca2967271af402a4d9a861927b))
* **api:** add subscriber CRUD endpoints with multitenancy ([9599036](https://github.com/ailianbr/prospect/commit/95990369c3207e7cb8a93f7fd2f5328b2ebbc496))
* **env:** three-env (dev/stg/prd) setup, self-seeding dev stack, ephemeral-stack CI ([23fe570](https://github.com/ailianbr/prospect/commit/23fe570766efe0896ec016e9ddebdb57d526e75b))


### Bug Fixes

* **api:** resolve lint errors in subscriber endpoints ([a7d820c](https://github.com/ailianbr/prospect/commit/a7d820cd9030e3637540879c7589bd22189c225f))

## [0.5.0](https://github.com/Kerryhen/monk/compare/monk-api-v0.4.3...monk-api-v0.5.0) (2026-03-30)


### Features

* **api:** replace per-request PB login with self-refreshing token ([#39](https://github.com/Kerryhen/monk/issues/39)) ([a0b0df5](https://github.com/Kerryhen/monk/commit/a0b0df582114d5815428ec353c0a2a08869885fd)), closes [#37](https://github.com/Kerryhen/monk/issues/37)
* release development → main ([c2a336c](https://github.com/Kerryhen/monk/commit/c2a336caa509f3fb052e918deff734ee281f1d8b))


### Bug Fixes

* **chatwoot:** log which PocketBase collection fails in fetch_chatwoot_config ([f25f993](https://github.com/Kerryhen/monk/commit/f25f99354ba7e47702a462c885eb22427f3bb4f1))
* **infra:** isolate prd and stg docker networks + add client_id to logs ([#38](https://github.com/Kerryhen/monk/issues/38)) ([35eeae9](https://github.com/Kerryhen/monk/commit/35eeae9eb65aff1cc98492117ec58aa3b9e6701a))

## [0.4.3](https://github.com/Kerryhen/monk/compare/monk-api-v0.4.2...monk-api-v0.4.3) (2026-03-26)


### Bug Fixes

* **api:** set default_list when existing default was cascade-deleted ([#34](https://github.com/Kerryhen/monk/issues/34)) ([869d401](https://github.com/Kerryhen/monk/commit/869d401f7afe18f7e3481d9f703045922a1823f5))

## [0.4.2](https://github.com/Kerryhen/monk/compare/monk-api-v0.4.1...monk-api-v0.4.2) (2026-03-26)


### Bug Fixes

* **api:** recover from stale PocketBase relation IDs in create/delete list ([#32](https://github.com/Kerryhen/monk/issues/32)) ([318720e](https://github.com/Kerryhen/monk/commit/318720ecaba911ebe144bc8bea84c625f85bc75f))

## [0.4.1](https://github.com/Kerryhen/monk/compare/monk-api-v0.4.0...monk-api-v0.4.1) (2026-03-26)


### Bug Fixes

* **api:** clarify version import comment ([#29](https://github.com/Kerryhen/monk/issues/29)) ([32c9b33](https://github.com/Kerryhen/monk/commit/32c9b33f3c0e5191c9a040003db9629eb01d72b5))

## [0.4.0](https://github.com/Kerryhen/monk/compare/monk-api-v0.3.0...monk-api-v0.4.0) (2026-03-26)


### Features

* **api:** add GET /v1/client and fix invalid list_id on subscriber import ([c2c0269](https://github.com/Kerryhen/monk/commit/c2c02693b5379b7f43d65715255f19ca76523478))
* **api:** add GET /v1/client endpoint and fix invalid list_id on subscriber import ([fe5082d](https://github.com/Kerryhen/monk/commit/fe5082da4f7f265d4ad0a91412a65f7f985cb201))
* **api:** add instance_id and user_agent to wide events; fix unstructured log ([01f12d7](https://github.com/Kerryhen/monk/commit/01f12d7883b4c472af412c53ebfa4d98a1378306))
* **api:** auto-create client and default list on first subscriber import ([d2e180b](https://github.com/Kerryhen/monk/commit/d2e180bd17a3166eea39857af50afadec653282e))
* **api:** auto-create client and default list on first subscriber import ([e336e8b](https://github.com/Kerryhen/monk/commit/e336e8bcc9783e4f61be4d022fde2c38a5b33972))
* **api:** client info, import edge cases, campaign auth fix, e2e test ([5db002b](https://github.com/Kerryhen/monk/commit/5db002b2bdba15a1f359ce90b075c914658861e2))
* **api:** client info, import edge cases, campaign auth fix, e2e test ([5db002b](https://github.com/Kerryhen/monk/commit/5db002b2bdba15a1f359ce90b075c914658861e2))
* **api:** default campaign type to 'regular' and add schema unit tests ([fded111](https://github.com/Kerryhen/monk/commit/fded1110da4761c0928e6410665063e4a9b45901))
* **api:** default list type to 'private' ([6d2de4f](https://github.com/Kerryhen/monk/commit/6d2de4f57a7d2dee572b68827c7012be0e088498))
* **api:** implement wide-event logging with JSON output ([24d14f9](https://github.com/Kerryhen/monk/commit/24d14f9e36ed2e25efc1abbc02ea6e02abc88606))
* **api:** integrate OpenTelemetry tracing (opt-in via env var) ([3c453dc](https://github.com/Kerryhen/monk/commit/3c453dc5e023842b2475c2b6e3138ea2e1bf4320))
* **api:** mount all routes under /api/v1 in addition to /v1 ([00a97df](https://github.com/Kerryhen/monk/commit/00a97dfd705dc40a5f65cd0894417f0d3618c89c))
* **api:** OpenTelemetry observability integration ([bb3ebab](https://github.com/Kerryhen/monk/commit/bb3ebabbbe755dfe9dfc387e7754d55f6d7794ee))
* **channels:** add schema and template provider endpoints ([c76b9ad](https://github.com/Kerryhen/monk/commit/c76b9ad673c6ff19e453875f457a9975aabd2dfa))
* **channels:** dynamic handler routing, x-instance-id header, endpoint docs ([d8f633e](https://github.com/Kerryhen/monk/commit/d8f633ee3f432414e9634d18541995c0b7cc4dec))
* **channels:** dynamic handler routing, x-instance-id header, endpoint docs ([61341f4](https://github.com/Kerryhen/monk/commit/61341f446ce927c1fa39c905de054d0ccd8d4771))
* **channels:** fetch templates from Chatwoot API ([e3fd608](https://github.com/Kerryhen/monk/commit/e3fd608b07d9a734762ebc147cd370b7f2468972))
* **channels:** fetch templates from Chatwoot API (P-01 Option A) ([dd53c00](https://github.com/Kerryhen/monk/commit/dd53c00f22cb525a9dc8e5298fd52b185ca94d95))
* **channels:** migrate Chatwoot config to multi-collection PocketBase schema ([34454d9](https://github.com/Kerryhen/monk/commit/34454d90e0c6ebebda377e4fbee1dd86749f43bc))
* **chatwoot:** align campaign body schema to consumer format ([b8c76e9](https://github.com/Kerryhen/monk/commit/b8c76e903939fc227b62e3398b7073fa075a8a04))
* **chatwoot:** WhatsApp campaign body schema + template API ([c280432](https://github.com/Kerryhen/monk/commit/c280432127e76746c6a07634c6d50e8b3d240eba))
* **docs:** replace Swagger UI with Scalar API reference ([4c18dfa](https://github.com/Kerryhen/monk/commit/4c18dfaec7febd4f764ab1d71ef74dda02a45394))
* **handlers:** Chatwoot handler + channel routes ([0f77f98](https://github.com/Kerryhen/monk/commit/0f77f98116f8814bbd3627a438a138d49ad4c782))
* **handlers:** Chatwoot handler + channel routes ([0f77f98](https://github.com/Kerryhen/monk/commit/0f77f98116f8814bbd3627a438a138d49ad4c782))
* **handlers:** implement ChatwootHandler with integration tests ([d14b0eb](https://github.com/Kerryhen/monk/commit/d14b0ebc9d13468186477e1df5243d7d4a79023d))
* **handlers:** implement ChatwootHandler with variable resolver and tests ([402c5a3](https://github.com/Kerryhen/monk/commit/402c5a3af486c979b8bcc28974089f80ffc5b54f))
* **handlers:** implement DefaultVariableResolver with unit tests ([dfb616c](https://github.com/Kerryhen/monk/commit/dfb616c6a4c896115af1efc1f54c59a3f9b4d1cc))
* **infra:** inject instance tag on campaign creation; add monk_channel_configs ([774f7ce](https://github.com/Kerryhen/monk/commit/774f7ce499e678780b30ae63002e90c860e700ef))
* merge development into main ([6f5da37](https://github.com/Kerryhen/monk/commit/6f5da3701ad1ebdc9b343e196d93bb985a40ce7c))
* **observability:** replace otel-collector with grafana/otel-lgtm ([f6a98e1](https://github.com/Kerryhen/monk/commit/f6a98e174628f97b7ac66e33667cbe62ea6642a9))


### Bug Fixes

* **api:** add enum validators and min_length to schemas per Listmonk spec ([88cb3d3](https://github.com/Kerryhen/monk/commit/88cb3d315d0f61a45ddd461cb3e5124da712ef93))
* **api:** add valid Swagger examples to campaign, list and subscriber schemas ([37268fc](https://github.com/Kerryhen/monk/commit/37268fc7eb3f9cb3d673b2a264c9d854bf3a2847))
* **api:** add visual content_type, ENVIRONMENT error handler, and forward Listmonk errors ([0ad0625](https://github.com/Kerryhen/monk/commit/0ad06256157ad58843e7b023288931f71d566af0))
* **api:** forward Listmonk error responses instead of raising 500 ([9e1f0c3](https://github.com/Kerryhen/monk/commit/9e1f0c36abb4648c296461ec6b8d0139b279f1fa))
* **api:** remove Basic Auth dependency from campaign and messenger routers ([1719cbf](https://github.com/Kerryhen/monk/commit/1719cbf77953775fba58544a22e1a7c77ada994d))
* **api:** remove spurious auth on subscriber import and return empty list for unknown client ([f7dd09e](https://github.com/Kerryhen/monk/commit/f7dd09ecd91e7bdb1bcfc1bffccc614c7b873184))
* **api:** remove trailing slash from root collection routes ([e4b3bc5](https://github.com/Kerryhen/monk/commit/e4b3bc58c9be1ecf69a4172acf220f74506ee48e))
* **api:** return empty list for unknown client on GET campaigns ([3135f8d](https://github.com/Kerryhen/monk/commit/3135f8d08490917752e355e43bd089ab318b540e))
* **api:** serialize datetime fields with mode='json' in campaign payloads ([c28f4cd](https://github.com/Kerryhen/monk/commit/c28f4cde160085849f986391b484c7d769284320))
* **api:** validate email format on JSON subscriber import ([8b297ae](https://github.com/Kerryhen/monk/commit/8b297aeb8b4d08fb2d3f6df853f9c5bd62fa14e4))
* **campaign:** clear WhatsApp template content before storing in Listmonk ([d6de241](https://github.com/Kerryhen/monk/commit/d6de2412d7462e2ac3e0e66a116ddafab979d8f1))
* **campaign:** force passthrough template for non-email messenger campaigns ([3b96cdc](https://github.com/Kerryhen/monk/commit/3b96cdc57280f6b3f6e6e1848856c6ea279869cd))
* **chatwoot:** log chatwoot api error status/body and add campaign context to skip logs ([a8fb8a6](https://github.com/Kerryhen/monk/commit/a8fb8a6d1c0578981c6a1df0099d2c7f54ead385))
* **observability:** log Listmonk error detail in wide event on upstream errors ([98f3d21](https://github.com/Kerryhen/monk/commit/98f3d21185763c1721c1b87cb212ea608760c84b))


### Documentation

* **api:** add best practices documentation ([d4fc345](https://github.com/Kerryhen/monk/commit/d4fc345987a9c15800061c4f2189263a96f98e2d))
* **api:** add HTTP request examples file ([dfa232c](https://github.com/Kerryhen/monk/commit/dfa232ce73f473050c4e55c3f14017420bf6b86b))
* **campaign:** document WhatsApp flow, resolver syntax, and helper endpoints ([3ac83b8](https://github.com/Kerryhen/monk/commit/3ac83b8ab56e1ac41ecf6c7b2e0042227c9d8f95))

## [0.3.0](https://github.com/Kerryhen/monk/compare/monk-api-v0.2.0...monk-api-v0.3.0) (2026-03-13)


### Features

* **api:** add GET /v1/list endpoint returning client-scoped lists ([a42e54a](https://github.com/Kerryhen/monk/commit/a42e54ad5bd508c4835d6121982a91c4d09b4990))


### Bug Fixes

* **api:** add exponential backoff retry on timeout and network errors ([9434c99](https://github.com/Kerryhen/monk/commit/9434c9998982d416719f7e24ea30e7d5b89cd8c1))
* **api:** add exponential backoff retry on timeout and network errors in Monk client ([ff3ac9b](https://github.com/Kerryhen/monk/commit/ff3ac9b3fed2e1608ec3ca39ad9c6fe27edd4b01))
* **api:** set FastAPI version from package metadata ([5d7eb0e](https://github.com/Kerryhen/monk/commit/5d7eb0ece2bc6a362465e20f51924fc00b5b8fbc))
* **api:** set FastAPI version from package metadata ([6d162f4](https://github.com/Kerryhen/monk/commit/6d162f4cdb7c2ec881b04f4dc90181653abf5132))

## [0.2.0](https://github.com/Kerryhen/monk/compare/monk-api-v0.1.1...monk-api-v0.2.0) (2026-03-12)


### Features

* **api:** add /v1 URL prefix and release automation ([ea1a2e7](https://github.com/Kerryhen/monk/commit/ea1a2e711e1a5828cb80d904554dc1685fbb4a31))
* **api:** implement campaign management with client ownership ([0e0ca16](https://github.com/Kerryhen/monk/commit/0e0ca16f3a3aa1bfefc522c78a9de0b4e840e08c))
* **api:** migrate client identifier from query param to X-Instance-ID header ([1560d33](https://github.com/Kerryhen/monk/commit/1560d337ef02488b5756a757ad759e8313a4e176))
* **messenger:** add messenger gateway with pluggable handler registry ([7dfe104](https://github.com/Kerryhen/monk/commit/7dfe1047f0f82379ff0449205e2540846ff553a3))
* **observability:** add structured logging across interface and sessions ([06b21f7](https://github.com/Kerryhen/monk/commit/06b21f799d8880f90dde32d8d44f338da04bee4b))
* **subscribers:** add JSON import endpoint ([12fc58a](https://github.com/Kerryhen/monk/commit/12fc58a70fe031e267151dbd0bce328fa86bb247))
* **subscribers:** add JSON import endpoint ([12fc58a](https://github.com/Kerryhen/monk/commit/12fc58a70fe031e267151dbd0bce328fa86bb247))
* **subscribers:** add JSON import endpoint with list ownership fallback ([8470d5e](https://github.com/Kerryhen/monk/commit/8470d5e9e0cb64aa71ad1d2f08013d6a6555a0ac))
* **subscribers:** implement CSV import endpoint with default list tracking ([5420944](https://github.com/Kerryhen/monk/commit/542094451358891eb717aa06800d9877b962baed))
* **tests:** add campaign start/stop tests and fake handler capture ([fea3c50](https://github.com/Kerryhen/monk/commit/fea3c50d3626ef1266567686a4907ca88af0e85d))


### Bug Fixes

* **campaigns:** enforce ownership on list updates and add missing auth tests ([43aa56d](https://github.com/Kerryhen/monk/commit/43aa56de17a2b6f75b05cafbca496170dba7b296))
* **subscribers:** enforce list ownership on import and add cleanup ([9f86adc](https://github.com/Kerryhen/monk/commit/9f86adc4de8187e83be5df28c0e11a30409a6693))


### Documentation

* **messenger:** add handler guide with integration example ([3f61280](https://github.com/Kerryhen/monk/commit/3f612805c079535b918d64e1ef08e39c727a83cb))
* **observability:** add logging guide with OTel migration path ([183018f](https://github.com/Kerryhen/monk/commit/183018ff12741d23c850579ecb7638e9185d4679))
