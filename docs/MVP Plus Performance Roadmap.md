# MVP Plus Performance Roadmap

This roadmap extends the public EDGP MVP with performance work that keeps the
current dependency-free core usable while leaving room for optional accelerated
backends. The name "MVP Plus" is intentional: these are production-shaping
steps after the public MVP, but before claiming a full production system.

## Loop Discipline

Every roadmap item should be developed as a vertical slice:

1. Plan the smallest measurable change.
2. Implement it behind the existing public CLI/report contracts.
3. Add unit coverage and smoke coverage where the behavior is public.
4. Validate locally.
5. Validate on the AlmaLinux VPS when runtime behavior can differ by host.
6. Commit and push the vertical.
7. Reassess the next roadmap item using the new benchmark evidence.

## Roadmap Items

1. **Reverse CSR Sidecar**
   Materialize reverse dependency arrays beside the existing forward CSR arrays:
   `reverse_values`, `reverse_column_indices`, and `reverse_row_pointers`.
   This turns dependent lookups from full-graph scans into direct row-slice
   reads and should immediately improve impact, advisory, and libsolv bridge
   workflows.

2. **Integer-Native Traversal**
   Add internal traversal APIs that operate on vertex ids instead of package-id
   strings. Convert ids back to package strings only at the CLI, JSON, and HTML
   boundaries. This removes repeated string dictionary lookups from hot loops.

3. **Vectorized Ranking**
   Replace Python edge iteration in most-depended-upon ranking with NumPy
   counting over `column_indices`, for example with `np.bincount`. Keep stable
   tie-breaking by package id after the count vector is computed.

4. **Frozen Graph Runtime**
   Split mutable graph construction from immutable traversal with a frozen CSR
   runtime. Builders can keep Python dictionaries while ingestion is active;
   traversal receives a compact immutable object with forward and reverse
   arrays, metadata maps, and predictable memory accounting.

5. **Optional Numba Kernels**
   Add an optional `edgp[fast]` backend for Numba-compiled traversal kernels.
   Candidate kernels include forward reachability, reverse reachability,
   shortest path parent arrays, and top-k indegree. The pure NumPy/Python path
   remains the portable default.

6. **Memory-Mapped Graph Artifacts**
   Persist frozen graph arrays as `.npy` or `.npz` artifacts so large public RPM
   repository graphs can be loaded without rebuilding from XML every time.
   This should include manifest metadata, digest checks, and versioned layout
   fields.

7. **GraphBLAS Backend Experiments**
   Add an optional GraphBLAS backend for batch traversal and sparse linear
   algebra workloads such as multi-source reachability. The core EDGP contract
   remains CSR graph snapshots and report bundles; GraphBLAS is an acceleration
   backend, not the canonical storage format.

8. **Parallel Query Execution**
   Use immutable arrays and optional native kernels to run independent queries
   concurrently. The long-term target is Python 3.14 free-threaded builds for
   Python-level orchestration plus native array kernels for hot traversal.

## Measurement Targets

Each performance vertical should extend deterministic benchmarks with at least
one relevant measurement:

- forward reachability latency;
- reverse reachability latency;
- shortest path latency;
- most-depended-upon ranking latency;
- storage bytes for forward and reverse arrays;
- whether all hot arrays are C-contiguous;
- behavior on local macOS and AlmaLinux VPS validation.

## Completed Verticals

- Reverse CSR sidecar:
  dependent lookups and reverse reachability now read direct reverse CSR row
  slices instead of scanning the full forward graph.
- Integer-native traversal:
  public string-based query methods now route through vertex-id traversal APIs
  and convert back to package ids only at the method boundary.
- Vectorized ranking:
  most-depended-upon ranking now counts incoming edges with NumPy over
  `column_indices` before applying stable package-id tie-breaking.
- Frozen graph runtime:
  mutable builders now expose `freeze()` for read-only `FrozenCSRGraph`
  snapshots, and synthetic benchmarks report freeze timing before traversal.
- Optional Numba kernels:
  `.[fast]` declares the optional Numba dependency, traversal accepts
  `python`, `auto`, or `numba` backends, and benchmark JSON reports accelerator
  availability plus the selected backend.
- Memory-mapped graph artifacts:
  `edgp csr-artifact` writes frozen CSR arrays as `.npy` files with a
  `manifest.json` containing layout version, package metadata, array shapes,
  SHA-256 digests, and a storage profile for contiguous read-only arrays; the
  loader verifies array digests, storage-profile byte totals, digest coverage,
  and memory-maps arrays by default.
- GraphBLAS backend experiments:
  `.[graphblas]` declares the optional `python-graphblas` dependency, and
  `edgp accelerator-status` reports availability plus candidate sparse linear
  algebra kernels while keeping frozen CSR as the canonical storage contract.
- Parallel query execution:
  `edgp parallel-query` freezes a snapshot-derived graph once and executes
  independent dependency/dependent reachability queries concurrently with a
  selected traversal backend. It can also load a verified memory-mapped CSR
  artifact directly for build-once/query-many workflows and render those
  results as verifiable static report bundles.
