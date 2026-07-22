<script lang="ts">
  const stats = [
    { label: "Tests", value: "256" },
    { label: "Domain Models", value: "19" },
    { label: "Benchmarks", value: "6" },
    { label: "ADRs", value: "7" },
    { label: "Runtimes", value: "2" },
  ];

  const stack = [
    "Python 3.12+",
    "Pydantic v2",
    "pytest + Hypothesis",
    "SQLite + JSONL",
    "httpx",
    "uv",
    "Typer CLI",
  ];

  const arch = [
    { label: "User Goal", accent: false },
    { label: "Goal Compiler", accent: true },
    { label: "Typed Plan DAG", accent: false },
    { label: "Deterministic Orchestrator", accent: false },
    { label: "Model Proposer", accent: true },
    { label: "Policy Verifier", accent: true },
    { label: "Sandbox Executor", accent: true },
    { label: "Event Ledger", accent: false, term: true },
  ];
</script>

<svelte:head>
  <title>Durable Agent Runtime Lab</title>
  <meta
    name="description"
    content="A comparative study on agentic reliability: evaluating conventional model-driven loops against deterministic, event-sourced workflow engines."
  />
</svelte:head>

<div class="min-h-screen selection:bg-cyan-500/30">
  <!-- Hero -->
  <header class="max-w-5xl mx-auto px-6 pt-24 pb-16 border-b border-slate-800">
    <div class="flex items-center gap-3 mb-6">
      <div class="bg-cyan-400/10 border border-cyan-400/20 px-3 py-1 rounded">
        <span class="font-mono text-xs tracking-widest text-cyan-400 uppercase"
          >Research Project</span
        >
      </div>
    </div>

    <h1 class="text-5xl md:text-6xl font-bold tracking-tight mb-6">
      Durable Agent <span class="text-slate-500">Runtime Lab</span>
    </h1>

    <p class="text-xl text-slate-400 max-w-2xl mb-8 leading-relaxed">
      A comparative study on agentic reliability — evaluating conventional
      model-driven loops against deterministic, event-sourced workflow engines.
    </p>

    <div class="flex flex-wrap gap-4 items-center mb-10">
      <a
        href="https://github.com/rmax-ai/durable-agent-runtime-lab"
        class="flex items-center gap-2 bg-slate-900 border border-slate-800 px-3 py-1 rounded-full text-sm hover:border-slate-600 transition-colors"
      >
        <span class="text-slate-400">⬡</span>
        <span class="font-mono">rmax-ai/durable-agent-runtime-lab</span>
      </a>
      <div
        class="flex items-center gap-2 bg-slate-900 border border-slate-800 px-3 py-1 rounded-full text-sm"
      >
        <span class="text-slate-400">⚖</span> <span>MIT License</span>
      </div>
      <div
        class="flex items-center gap-2 bg-slate-900 border border-slate-800 px-3 py-1 rounded-full text-sm font-mono text-cyan-400"
      >
        v0.2.0
      </div>
    </div>

    <div class="bg-slate-900 rounded-lg p-4 font-mono text-sm border border-slate-800 max-w-md">
      <div class="flex gap-2 mb-2 opacity-50">
        <div class="w-3 h-3 rounded-full bg-red-500/50"></div>
        <div class="w-3 h-3 rounded-full bg-yellow-500/50"></div>
        <div class="w-3 h-3 rounded-full bg-green-500/50"></div>
      </div>
      <div class="text-slate-400">
        <span class="text-cyan-400">$</span> uv sync --extra dev
      </div>
      <div class="text-slate-400">
        <span class="text-cyan-400">$</span> uv run dar experiment run
        --config experiments/configs/quickstart.yaml
      </div>
      <div class="text-slate-400">
        <span class="text-cyan-400">$</span> uv run dar experiment run
        --config experiments/configs/quickstart.yaml --provider openai
      </div>
    </div>
  </header>

  <!-- Thesis -->
  <section class="max-w-5xl mx-auto px-6 py-24">
    <h2 class="text-sm font-mono text-cyan-400 uppercase mb-8">The Thesis</h2>
    <blockquote class="text-3xl md:text-4xl font-medium leading-tight text-slate-100">
      "Long-horizon AI-agent reliability improves when stochastic model decisions are
      <span class="text-cyan-400"
        >compiled into typed, deterministic, durable, verifiable workflows</span
      >
      rather than executed through an unconstrained conversational tool loop."
    </blockquote>
  </section>

  <!-- Two Runtimes -->
  <section class="max-w-5xl mx-auto px-6 py-24 border-t border-slate-800">
    <h2 class="text-sm font-mono text-cyan-400 uppercase mb-12">Two Runtimes Compared</h2>
    <div class="grid md:grid-cols-2 gap-12">
      <!-- Baseline -->
      <div class="space-y-6">
        <h3 class="text-xl font-bold flex items-center gap-2">
          <span class="text-slate-500 text-lg">⟳</span> Baseline Runtime
        </h3>
        <p class="text-slate-400 text-sm">
          The conventional ReAct-style loop used by most current agent frameworks.
        </p>
        <ul class="space-y-3 text-sm font-mono">
          <li class="flex gap-3 text-slate-500">
            <span class="text-red-400">[✗]</span> Ad-hoc string-based tool calls
          </li>
          <li class="flex gap-3 text-slate-500">
            <span class="text-red-400">[✗]</span> Volatile execution state
          </li>
          <li class="flex gap-3 text-slate-500">
            <span class="text-red-400">[✗]</span> Opaque model reasoning
          </li>
          <li class="flex gap-3 text-slate-500">
            <span class="text-red-400">[✗]</span> Brittle error recovery
          </li>
        </ul>
      </div>

      <!-- Durable -->
      <div class="space-y-6 p-6 bg-cyan-400/5 border border-cyan-400/20 rounded-xl">
        <h3 class="text-xl font-bold flex items-center gap-2 text-cyan-400">
          <span class="text-lg">⊞</span> Durable Runtime
        </h3>
        <p class="text-slate-300 text-sm">
          A deterministic engine treating the model as a stochastic proposal generator
          within a formal state machine.
        </p>
        <ul class="space-y-3 text-sm font-mono">
          <li class="flex gap-3">
            <span class="text-cyan-400">[✓]</span> Typed Goal Specs &amp; Pydantic DAGs
          </li>
          <li class="flex gap-3">
            <span class="text-cyan-400">[✓]</span> Append-only event ledger (hash chained)
          </li>
          <li class="flex gap-3">
            <span class="text-cyan-400">[✓]</span> Proposal → Verify → Commit cycle
          </li>
          <li class="flex gap-3">
            <span class="text-cyan-400">[✓]</span> Idempotent sandboxed execution
          </li>
        </ul>
      </div>
    </div>
  </section>

  <!-- Architecture Pipeline -->
  <section class="bg-slate-900/50 py-24 border-y border-slate-800">
    <div class="max-w-5xl mx-auto px-6">
      <h2 class="text-sm font-mono text-cyan-400 uppercase mb-12 text-center">
        Architecture Pipeline
      </h2>
      <div
        class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 font-mono text-[11px] uppercase tracking-tighter"
      >
        {#each arch as item, i}
          {@const isAccent = item.accent}
          {@const isTerm = item.term ?? false}
          <div
            class="p-3 border text-center {isTerm
              ? 'bg-cyan-400 text-slate-950 font-bold border-cyan-400'
              : isAccent
                ? 'border-cyan-500/30 bg-slate-950 text-cyan-400'
                : 'border-slate-700 bg-slate-950 text-slate-300'}"
          >
            {#if i > 0}
              <div class="text-slate-600 text-xs mb-1">↓</div>
            {/if}
            {item.label}
          </div>
        {/each}
      </div>
    </div>
  </section>

  <!-- Key Numbers -->
  <section class="max-w-5xl mx-auto px-6 py-24">
    <div class="grid grid-cols-2 md:grid-cols-5 gap-8">
      {#each stats as stat}
        <div class="text-center">
          <div class="text-4xl font-bold text-white mb-1 font-mono">{stat.value}</div>
          <div class="text-xs font-mono text-slate-500 uppercase tracking-widest">
            {stat.label}
          </div>
        </div>
      {/each}
    </div>
  </section>

  <!-- Quick Start -->
  <section class="max-w-5xl mx-auto px-6 py-24 border-t border-slate-800">
    <h2 class="text-2xl font-bold mb-8 flex items-center gap-2">
      <span class="text-cyan-400 text-xl">▸</span> Quick Start
    </h2>
    <div class="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      <div
        class="px-4 py-2 border-b border-slate-800 bg-slate-800/50 text-xs font-mono text-slate-400"
      >
        Terminal
      </div>
      <pre
        class="p-6 text-sm font-mono overflow-x-auto text-slate-300"
      ><code># Clone and install
git clone https://github.com/rmax-ai/durable-agent-runtime-lab
cd durable-agent-runtime-lab
uv sync --extra dev

# Run tests
uv run pytest                # 256 tests

# Run an experiment (mock provider, no API key needed)
uv run dar experiment run --config experiments/configs/quickstart.yaml

# Run the same experiment with OpenAI (requires OPENAI_API_KEY)
UV_CACHE_DIR=.uv-cache uv run dar experiment run \
  --config experiments/configs/quickstart.yaml \
  --provider openai

# Generate the latest run report
uv run dar experiment report</code></pre>
    </div>
  </section>

  <!-- Stack -->
  <section class="bg-slate-900/30 py-16">
    <div class="max-w-5xl mx-auto px-6">
      <h3
        class="text-xs font-mono text-slate-500 uppercase mb-8 text-center tracking-[0.2em]"
      >
        Built with Modern Python
      </h3>
      <div class="flex flex-wrap justify-center gap-x-8 gap-y-4">
        {#each stack as item}
          <span class="text-sm font-mono text-slate-400">{item}</span>
        {/each}
      </div>
    </div>
  </section>

  <!-- Footer -->
  <footer
    class="max-w-5xl mx-auto px-6 py-12 border-t border-slate-800 flex flex-col md:flex-row justify-between items-center gap-6"
  >
    <div class="text-sm text-slate-500">
      &copy; 2026 Durable Agent Runtime Lab. MIT License.
    </div>
    <div class="flex gap-6 text-sm font-mono">
      <a
        href="https://github.com/rmax-ai/durable-agent-runtime-lab"
        class="hover:text-cyan-400 transition-colors text-slate-500"
      >
        GitHub
      </a>
      <a
        href="https://github.com/rmax-ai/durable-agent-runtime-lab/blob/main/docs/adr/README.md"
        class="hover:text-cyan-400 transition-colors text-slate-500"
      >
        ADRs
      </a>
      <a
        href="https://github.com/rmax-ai/durable-agent-runtime-lab/blob/main/README.md"
        class="hover:text-cyan-400 transition-colors text-slate-500"
      >
        Docs
      </a>
    </div>
  </footer>
</div>
