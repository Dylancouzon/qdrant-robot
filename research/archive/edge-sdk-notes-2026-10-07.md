# Historical Edge SDK survey, 2026-10-07

This survey preserves the original observations and external comparisons. Its release, upstream issue, and performance statements are dated. [Current pinned-runtime guidance](../qdrant-edge.md) owns project behavior.

# Qdrant Edge: what it can do

As of 2026-10-07. Verify against the installed package's `.pyi` stubs before relying on any line.

## Summary

- `qdrant-edge-py` 0.8.0 (2026-08-05) is the latest release. It ships `manylinux_2_28` aarch64 wheels; JetPack 6 has glibc 2.35.
- One query can fuse prefetches: `QueryRequest(prefetches=[...], query=Fusion.Rrf(k=2))`. **Tested on 0.7.2**: dense plus sparse RRF returned the expected order. Also present in the stubs: `Fusion.Dbsf`, weighted RRF, `Mmr`, `Formula` with `DecayKind` (Lin, Gauss, Exp), `Query.RecommendBestScore`, `RecommendSumScores`, `Discover`, `Context`, `FeedbackNaive`, `OrderBy`, `Sample`, `facet`, `count`, `scroll`.
- Built-in BM25: `Bm25`, `Bm25Config`, sparse vectors with the IDF modifier. Use `embed_document` for documents and `embed_query` for queries.
- Multivector with MaxSim: `EdgeVectorParams(multivector_config=MultiVectorConfig(MultiVectorComparator.MaxSim))`. Example: `lib/edge/python/examples/multivector-colbert.py` in qdrant/qdrant.
- Quantization: scalar, product, binary (1, 1.5, 2 bit), and TurboQuant (4, 2, 1.5, 1 bit). TurboQuant 4-bit is close to int8 recall at twice the compression. Binary 1-bit loses precision below about 1,000 dimensions. Quantization is set at create time.
- No background optimizer. Call `optimize()` after bulk writes; until then new points are brute-force searched.
- No built-in sync. The documented pattern: seed from a server shard snapshot (`unpack_snapshot`, `load`), refresh with a partial snapshot (`snapshot_manifest` to `POST /collections/{c}/shards/0/snapshot/partial/create`, then `update_from_snapshot`), push with your own dual-write queue. Edge cannot create snapshots.
- `query_groups` and `search_matrix` exist only in Rust.

## 0.8.0 compared to 0.7.2 (stub diff)

- New: `EdgeConfig(max_search_threads=, search_pool_core=)`, `MatchPrefix`, `prefix=` on `TextIndexParams`, `DisabledStemmer`, `IdfParams(corpus=Filter)`, `TurboQuantQuantizationConfig`.
- Changed: `on_disk_payload` defaults to `None` (keep the shard's value). Getters for `on_disk_payload`, `hnsw_config`, `optimizers` return `Optional`.
- **Not in 0.8.0** (checked in the wheel): `query_batch`, `QueryBatchRequest`, the `Memory` placement enum (Cold, Cached, Pinned). These are on `master`.

## Threading

- `max_search_threads` sizes a rayon pool inside the shard (default: CPUs times 4). `search_pool_core` pins it to one core, which keeps search off the cores the models use.
- The PyO3 bindings appear to hold the GIL during `query` (no `allow_threads` found in `lib/edge/python`). Calls from several Python threads may serialize. Measure in M0.5.

## Known open issues (recheck; recorded 2026-10-07)

- qdrant#10846: `MatchValue(True)` is stored as integer 1.
- qdrant#9066: an integer index drops range matches when combined with a non-matching match clause.
- qdrant#9241: no live reload; `close()` and `load()` to swap a shard.

## Numbers

- No published Qdrant or Edge latency on any Jetson. Ours will be the first public numbers we know of.
- Qdrant's June 2026 blog: 0.51 ms for a hybrid query in the demo's screenshot. A separate iPhone 16 Pro test: about 0.1 ms on device over 10,000 vectors against about 52 ms to Qdrant Cloud over cellular (not an official benchmark).

## Sources

- https://qdrant.tech/documentation/edge/edge-api/reading-data/
- https://qdrant.tech/documentation/edge/edge-vs-qdrant-cluster/
- https://qdrant.tech/documentation/edge/edge-synchronization-guide/
- https://qdrant.tech/documentation/edge/edge-data-synchronization-patterns/
- https://qdrant.tech/documentation/manage-data/quantization/
- https://pypi.org/project/qdrant-edge-py/
- https://github.com/qdrant/qdrant/tree/master/lib/edge/python/examples
- https://qdrant.tech/blog/qdrant-edge-on-device-vector-search/
