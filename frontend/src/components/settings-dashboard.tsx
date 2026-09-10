"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { toast } from "react-toastify/unstyled";

import {
  fetchLlmModels,
  fetchLlmSettings,
  fetchOutputSchema,
  saveLlmSettings,
  testLlmChat,
  testLlmEmbeddings,
} from "@/lib/api";
import type {
  LLMChatResponse,
  LLMEffort,
  LLMEmbedResponse,
  LLMModelInfo,
  LLMProvider,
  LLMSettings,
  OutputColumn,
  OutputSchemaPreview,
} from "@/lib/types";

const CARD = "rounded-card border border-line/80 bg-paper p-5 shadow-card";
const PRIMARY_BUTTON =
  "cursor-pointer rounded-control bg-cardinal px-4 py-2.5 font-semibold text-paper hover:bg-cardinal-dark disabled:cursor-not-allowed disabled:opacity-55 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-solid focus-visible:outline-cardinal";
const CONTROL =
  "rounded-control border border-line bg-paper px-3 py-2.5 font-normal text-ink focus:outline-2 focus:outline-offset-2 focus:outline-solid focus:outline-cardinal";

const PROVIDER_LABEL: Record<LLMProvider, string> = {
  stanford: "Stanford Gateway",
  openai: "OpenAI",
  anthropic: "Anthropic",
};

const EFFORTS: { id: LLMEffort; label: string }[] = [
  { id: "none", label: "None" },
  { id: "low", label: "Low" },
  { id: "medium", label: "Medium" },
  { id: "high", label: "High" },
];

export function SettingsDashboard() {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [models, setModels] = useState<LLMModelInfo[]>([]);
  const [provider, setProvider] = useState<LLMProvider>("stanford");
  const [chatModel, setChatModel] = useState("gpt-5-mini");
  const [embeddingModel, setEmbeddingModel] = useState(
    "text-embedding-ada-002",
  );
  const [effort, setEffort] = useState<LLMEffort>("medium");
  const [minConfidence, setMinConfidence] = useState("50");
  const [minGap, setMinGap] = useState("2.5");
  const [columns, setColumns] = useState<OutputColumn[]>([]);
  const [locked, setLocked] = useState<string[]>([]);
  const [schema, setSchema] = useState<OutputSchemaPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [ollamaOpen, setOllamaOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const toastId = toast.loading("Loading model settings…");
    Promise.all([fetchLlmSettings(), fetchLlmModels().catch((caught: unknown) => caught)])
      .then(([nextSettings, modelsOrError]) => {
        if (cancelled) return;
        applySettings(nextSettings);
        if (Array.isArray(modelsOrError)) {
          setModels(modelsOrError);
          setModelsError(null);
          toast.update(toastId, {
            render: `Loaded ${modelsOrError.length} models from ${PROVIDER_LABEL[nextSettings.provider]}.`,
            type: "success",
            isLoading: false,
            autoClose: 4000,
          });
        } else {
          const message =
            modelsOrError instanceof Error
              ? modelsOrError.message
              : "Could not load available models.";
          setModelsError(message);
          toast.update(toastId, {
            render: message,
            type: "warning",
            isLoading: false,
            autoClose: 6000,
          });
        }
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        const message =
          caught instanceof Error ? caught.message : "Could not load settings.";
        setError(message);
        toast.update(toastId, {
          render: message,
          type: "error",
          isLoading: false,
          autoClose: 6000,
        });
      });
    return () => {
      cancelled = true;
      toast.dismiss(toastId);
    };
  }, []);

  function applySettings(next: LLMSettings) {
    setSettings(next);
    setProvider(next.provider);
    setChatModel(next.chat_model);
    setEmbeddingModel(next.embedding_model);
    setEffort(next.reasoning_effort);
    setMinConfidence(String(next.match_min_confidence));
    setMinGap(String(next.match_min_gap));
    setColumns(next.output_columns.map((column) => ({ ...column })));
    setLocked(next.locked_columns);
    fetchOutputSchema().then(setSchema).catch(() => setSchema(null));
  }

  const chatModels = useMemo(
    () => models.filter((item) => item.kind === "chat").map((item) => item.id),
    [models],
  );
  const embeddingModels = useMemo(
    () =>
      models.filter((item) => item.kind === "embedding").map((item) => item.id),
    [models],
  );

  const columnsDirty =
    !!settings &&
    JSON.stringify(columns) !== JSON.stringify(settings.output_columns);

  const dirty =
    !!settings &&
    (provider !== settings.provider ||
      chatModel !== settings.chat_model ||
      embeddingModel !== settings.embedding_model ||
      effort !== settings.reasoning_effort ||
      minConfidence !== String(settings.match_min_confidence) ||
      minGap !== String(settings.match_min_gap) ||
      columnsDirty);

  const matchFault = useMemo(
    () => validateBound(minConfidence, "Minimum confidence")
      ?? validateBound(minGap, "Minimum lead"),
    [minConfidence, minGap],
  );

  const columnFault = useMemo(() => validateColumns(columns), [columns]);

  function updateColumn(index: number, patch: Partial<OutputColumn>) {
    setColumns((current) =>
      current.map((column, position) =>
        position === index ? { ...column, ...patch } : column,
      ),
    );
  }

  function addColumn() {
    setColumns((current) => [...current, { name: "", description: "" }]);
  }

  function removeColumn(index: number) {
    setColumns((current) => current.filter((_, position) => position !== index));
  }

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    const toastId = toast.loading("Saving model defaults…");
    try {
      const next = await saveLlmSettings({
        provider,
        chat_model: chatModel,
        embedding_model: embeddingModel,
        reasoning_effort: effort,
        match_min_confidence: Number(minConfidence),
        match_min_gap: Number(minGap),
        output_columns: columns,
      });
      applySettings(next);
      try {
        const nextModels = await fetchLlmModels();
        setModels(nextModels);
        setModelsError(null);
      } catch (caught: unknown) {
        const message =
          caught instanceof Error
            ? caught.message
            : "Could not reload available models.";
        setModelsError(message);
      }
      toast.update(toastId, {
        render: `Saved. Chat uses ${next.chat_model}.`,
        type: "success",
        isLoading: false,
        autoClose: 4500,
      });
    } catch (caught: unknown) {
      const message =
        caught instanceof Error ? caught.message : "Could not save settings.";
      toast.update(toastId, {
        render: message,
        type: "error",
        isLoading: false,
        autoClose: 6000,
      });
    } finally {
      setSaving(false);
    }
  }

  if (error) {
    return (
      <p className="rounded-control bg-fail/10 px-3.5 py-3 leading-relaxed text-fail">
        {error}
      </p>
    );
  }

  if (!settings) {
    return <p className="text-muted">Loading model settings…</p>;
  }

  const configured = settings.configured;

  return (
    <div className="grid gap-6">
      <section className="grid gap-3 sm:grid-cols-3">
        <Stat
          label="Provider"
          value={PROVIDER_LABEL[settings.provider]}
          hint={dirty ? "Unsaved changes" : "Saved default"}
        />
        <Stat
          label="Chat model"
          value={settings.chat_model}
          hint={`${chatModels.length} chat models available`}
        />
        <Stat
          label="Effort"
          value={settings.reasoning_effort}
          hint={`Embeddings: ${settings.embedding_model}`}
        />
      </section>

      <form className={`${CARD} grid gap-5`} onSubmit={onSave}>
        <div>
          <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
            Defaults
          </p>
          <h2 className="font-serif text-[1.55rem] font-semibold tracking-tight">
            Models to use always
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
            The checker calls models through the backend router. Pick a live
            provider, then the chat and embedding models every request should
            use.
          </p>
        </div>

        <fieldset className="grid gap-2 border-0 p-0">
          <legend className="mb-1 text-sm font-semibold">Provider</legend>
          <div className="grid gap-2">
            <ProviderButton
              label="Stanford Gateway"
              hint={
                configured.stanford
                  ? "Live Stanford AI API Gateway"
                  : "Add AI_GATEWAY_API_KEY"
              }
              selected={provider === "stanford"}
              disabled={!configured.stanford}
              onClick={() => setProvider("stanford")}
            />
            <ProviderButton
              label="Ollama"
              hint="Placeholder fallback"
              selected={false}
              onClick={() => setOllamaOpen(true)}
            />
            <ProviderButton
              label="OpenAI"
              hint={
                configured.openai
                  ? "Direct OpenAI API"
                  : "Add OPENAI_API_KEY to enable"
              }
              selected={provider === "openai"}
              disabled={!configured.openai}
              onClick={() => setProvider("openai")}
            />
            <ProviderButton
              label="Anthropic"
              hint={
                configured.anthropic
                  ? "Direct Anthropic API"
                  : "Add ANTHROPIC_API_KEY to enable"
              }
              selected={provider === "anthropic"}
              disabled={!configured.anthropic}
              onClick={() => setProvider("anthropic")}
            />
          </div>
        </fieldset>

        {provider !== settings.provider ? (
          <p className="rounded-control bg-warn/10 px-3.5 py-3 text-sm leading-relaxed text-warn">
            Save defaults to switch providers and reload that model list. Tests
            still use {PROVIDER_LABEL[settings.provider]} until then.
          </p>
        ) : null}

        {modelsError ? (
          <p className="rounded-control bg-fail/10 px-3.5 py-3 text-sm leading-relaxed text-fail">
            {modelsError}
          </p>
        ) : null}

        <div className="grid gap-4 md:grid-cols-3">
          <label className="grid gap-1.5 text-sm font-semibold">
            Chat model
            <select
              className={CONTROL}
              value={chatModel}
              onChange={(event) => setChatModel(event.target.value)}
            >
              {ensureOption(chatModels, chatModel).map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1.5 text-sm font-semibold">
            Embedding model
            <select
              className={CONTROL}
              value={embeddingModel}
              onChange={(event) => setEmbeddingModel(event.target.value)}
            >
              {ensureOption(embeddingModels, embeddingModel).map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1.5 text-sm font-semibold">
            Reasoning effort
            <select
              className={CONTROL}
              value={effort}
              onChange={(event) =>
                setEffort(event.target.value as LLMEffort)
              }
            >
              {EFFORTS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="border-t border-line/70 pt-5">
          <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
            Structured output
          </p>
          <h2 className="font-serif text-[1.55rem] font-semibold tracking-tight">
            Columns {chatModel} must return
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
            Each column becomes one field in the JSON schema sent with every
            verdict call. The description is the instruction the model reasons
            against, so write it as a question about the requirement. The four
            required columns cannot be renamed or removed — the findings report
            is built from them. Every row also carries a{" "}
            <code className="font-mono text-[0.85em]">sources</code> list of the
            chunks the model used, which is what makes evidence clickable and
            highlighted.
          </p>
        </div>

        <div className="grid gap-3">
          {columns.map((column, index) => {
            const isLocked = locked.includes(column.name);
            return (
              <div
                key={isLocked ? column.name : `custom-${index}`}
                className="grid gap-2 rounded-control border border-line bg-sand/40 p-3 md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)_auto] md:items-start"
              >
                <div className="grid gap-1.5">
                  <input
                    className={`${CONTROL} w-full font-mono text-sm disabled:opacity-70`}
                    value={column.name}
                    disabled={isLocked}
                    placeholder="column_name"
                    aria-label={`Column ${index + 1} name`}
                    onChange={(event) =>
                      updateColumn(index, { name: event.target.value })
                    }
                  />
                  {isLocked ? (
                    <span className="text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-muted">
                      Required
                    </span>
                  ) : null}
                </div>
                <textarea
                  className={`${CONTROL} min-h-20 w-full resize-y text-sm`}
                  value={column.description}
                  rows={2}
                  placeholder="What should the model decide for this column?"
                  aria-label={`Column ${index + 1} description`}
                  onChange={(event) =>
                    updateColumn(index, { description: event.target.value })
                  }
                />
                <button
                  type="button"
                  onClick={() => removeColumn(index)}
                  disabled={isLocked}
                  aria-label={`Remove column ${column.name || index + 1}`}
                  className="cursor-pointer rounded-control border border-line px-3 py-2.5 text-sm font-semibold hover:border-fail hover:text-fail disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-line disabled:hover:text-ink"
                >
                  Remove
                </button>
              </div>
            );
          })}
        </div>

        <fieldset className="grid gap-3 border-0 p-0">
          <legend className="mb-1 text-sm font-semibold">Match rule</legend>
          <p className="max-w-2xl text-sm leading-relaxed text-muted">
            A document counts as matching a standard only if the top policy
            clears both tests. Cosine scores from{" "}
            <code className="rounded bg-cardinal/10 px-1 py-0.5 text-[0.85em]">
              text-embedding-ada-002
            </code>{" "}
            sit in a narrow band, so the lead over the runner-up separates a real
            match far better than the raw score does.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1.5 text-sm">
              <span className="font-semibold">Minimum confidence</span>
              <input
                type="number"
                min={0}
                max={100}
                step={0.5}
                inputMode="decimal"
                value={minConfidence}
                onChange={(event) => setMinConfidence(event.target.value)}
                className={CONTROL}
              />
              <span className="text-muted">
                Floor on the top score. A weak field fails outright.
              </span>
            </label>
            <label className="grid gap-1.5 text-sm">
              <span className="font-semibold">Minimum lead over runner-up</span>
              <input
                type="number"
                min={0}
                max={100}
                step={0.1}
                inputMode="decimal"
                value={minGap}
                onChange={(event) => setMinGap(event.target.value)}
                className={CONTROL}
              />
              <span className="text-muted">
                How far clear the best policy must be. An unrelated document
                scores about the same against everything, so its lead is near
                zero.
              </span>
            </label>
          </div>
          <p className="rounded-control bg-cardinal/5 px-3.5 py-3 text-sm leading-relaxed text-muted">
            Current rule: a match needs a top score of at least{" "}
            <strong className="text-ink">{minConfidence || "—"}%</strong> and a
            lead of at least{" "}
            <strong className="text-ink">{minGap || "—"}</strong> points over the
            second-placed policy.
          </p>
        </fieldset>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={addColumn}
            className="cursor-pointer rounded-control border border-line px-4 py-2.5 text-sm font-semibold hover:border-ink"
          >
            Add column
          </button>
          <span className="text-sm text-muted">
            {columns.length} columns + sources
          </span>
        </div>

        {matchFault ? (
          <p className="rounded-control bg-fail/10 px-3.5 py-3 text-sm leading-relaxed text-fail">
            {matchFault}
          </p>
        ) : null}

        {columnFault ? (
          <p className="rounded-control bg-fail/10 px-3.5 py-3 text-sm leading-relaxed text-fail">
            {columnFault}
          </p>
        ) : null}

        {columnsDirty && !columnFault ? (
          <p className="rounded-control bg-warn/10 px-3.5 py-3 text-sm leading-relaxed text-warn">
            Save to rebuild the schema below. Changing columns does not
            re-embed the policy library.
          </p>
        ) : null}

        <div>
          <button
            type="submit"
            className={PRIMARY_BUTTON}
            disabled={saving || !!columnFault || !!matchFault}
          >
            {saving ? "Saving…" : "Save defaults"}
          </button>
        </div>
      </form>

      {schema ? <SchemaPreview schema={schema} model={settings.chat_model} /> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <ChatTest
          model={chatModel}
          effort={effort}
          disabled={provider !== settings.provider}
        />
        <EmbedTest
          model={embeddingModel}
          disabled={provider !== settings.provider}
        />
      </div>

      {ollamaOpen ? <OllamaPlaceholder onClose={() => setOllamaOpen(false)} /> : null}
    </div>
  );
}

function ensureOption(ids: string[], selected: string): string[] {
  if (ids.includes(selected) || !selected) return ids;
  return [selected, ...ids];
}

const COLUMN_NAME_RE = /^[a-z][a-z0-9_]{0,39}$/;

/** Mirrors normalize_columns in backend/llm/schema.py so errors show as you type. */
function validateColumns(columns: OutputColumn[]): string | null {
  const seen = new Set<string>();
  for (const column of columns) {
    const name = column.name.trim().toLowerCase();
    if (!COLUMN_NAME_RE.test(name)) {
      return `Column name "${column.name || "(empty)"}" is invalid. Use lowercase letters, digits, and underscores, starting with a letter.`;
    }
    if (!column.description.trim()) {
      return `Column "${name}" needs a description.`;
    }
    if (column.description.trim().length > 600) {
      return `Description for "${name}" is too long (limit 600 characters).`;
    }
    if (seen.has(name)) {
      return `Duplicate column name "${name}".`;
    }
    seen.add(name);
  }
  if (columns.length > 16) {
    return "Too many columns. The limit is 16 including the 4 required ones.";
  }
  return null;
}

function validateBound(raw: string, label: string): string | null {
  const value = raw.trim();
  if (!value) return `${label} is required.`;
  const number = Number(value);
  if (!Number.isFinite(number)) return `${label} must be a number.`;
  if (number < 0 || number > 100) return `${label} must be between 0 and 100.`;
  return null;
}

function SchemaPreview({
  schema,
  model,
}: {
  schema: OutputSchemaPreview;
  model: string;
}) {
  const [tab, setTab] = useState<"prompt" | "schema">("prompt");
  const body =
    tab === "prompt"
      ? schema.system_prompt
      : JSON.stringify(schema.json_schema, null, 2);

  return (
    <section className={`${CARD} grid gap-4`}>
      <div>
        <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
          Saved
        </p>
        <h2 className="font-serif text-[1.45rem] font-semibold tracking-tight">
          What {model} receives
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
          Compiled from the saved columns. This exact pair goes out with every
          verdict call, so a change here is a change to every finding.
        </p>
      </div>

      <div className="flex gap-2">
        {(["prompt", "schema"] as const).map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            aria-pressed={tab === id}
            className={`cursor-pointer rounded-control border px-3.5 py-2 text-sm font-semibold ${
              tab === id
                ? "border-cardinal bg-cardinal/10"
                : "border-line hover:border-ink"
            }`}
          >
            {id === "prompt" ? "System prompt" : "JSON schema"}
          </button>
        ))}
      </div>

      <pre className="max-h-96 overflow-auto rounded-control border border-line bg-sand/60 px-3.5 py-3 font-mono text-xs leading-relaxed">
        {body}
      </pre>

      <p className="text-sm text-muted">
        Verdicts: {schema.verdicts.join(", ")}
      </p>
    </section>
  );
}

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <article className={CARD}>
      <p className="text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
        {label}
      </p>
      <p className="mt-2 truncate font-serif text-[1.65rem] font-semibold leading-tight tracking-tight">
        {value}
      </p>
      <p className="mt-2 text-sm text-muted">{hint}</p>
    </article>
  );
}

function ProviderButton({
  label,
  hint,
  selected,
  disabled = false,
  onClick,
}: {
  label: string;
  hint: string;
  selected: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={selected}
      className={`cursor-pointer rounded-control border px-4 py-3 text-left disabled:cursor-not-allowed disabled:opacity-55 ${
        selected
          ? "border-cardinal bg-cardinal/10"
          : "border-line bg-transparent hover:border-ink"
      }`}
    >
      <span className="block text-sm font-semibold">{label}</span>
      <span className="mt-0.5 block text-xs text-muted">{hint}</span>
    </button>
  );
}

function ChatTest({
  model,
  effort,
  disabled,
}: {
  model: string;
  effort: LLMEffort;
  disabled: boolean;
}) {
  const [prompt, setPrompt] = useState("Reply with one short sentence.");
  const [result, setResult] = useState<LLMChatResponse | null>(null);
  const [fault, setFault] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setRunning(true);
    setFault(null);
    const toastId = toast.loading("Testing chat completion…");
    try {
      const response = await testLlmChat({
        prompt,
        model,
        reasoning_effort: effort,
      });
      setResult(response);
      toast.update(toastId, {
        render: `Chat responded with ${response.model}.`,
        type: "success",
        isLoading: false,
        autoClose: 4500,
      });
    } catch (caught: unknown) {
      const message =
        caught instanceof Error ? caught.message : "Chat test failed.";
      setFault(message);
      setResult(null);
      toast.update(toastId, {
        render: message,
        type: "error",
        isLoading: false,
        autoClose: 6000,
      });
    } finally {
      setRunning(false);
    }
  }

  return (
    <form className={`${CARD} grid gap-4`} onSubmit={onSubmit}>
      <div>
        <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
          Test
        </p>
        <h2 className="font-serif text-[1.45rem] font-semibold tracking-tight">
          Chat completion
        </h2>
      </div>
      <label className="grid gap-1.5 text-sm font-semibold">
        Prompt
        <textarea
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          rows={4}
          className={`${CONTROL} min-h-28 resize-y`}
        />
      </label>
      <button
        type="submit"
        className={PRIMARY_BUTTON}
        disabled={running || disabled || !prompt.trim()}
      >
        {running ? "Sending…" : "Run chat test"}
      </button>
      {fault ? (
        <p className="rounded-control bg-fail/10 px-3.5 py-3 text-sm leading-relaxed text-fail">
          {fault}
        </p>
      ) : null}
      {result ? (
        <div className="rounded-control border border-line bg-sand/60 px-3.5 py-3">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">
            {result.model}
            {result.reasoning_effort ? ` · effort ${result.reasoning_effort}` : ""}
          </p>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">
            {result.content || "(empty response)"}
          </p>
        </div>
      ) : null}
    </form>
  );
}

function EmbedTest({
  model,
  disabled,
}: {
  model: string;
  disabled: boolean;
}) {
  const [input, setInput] = useState(
    "The quick brown fox jumps over the lazy dog",
  );
  const [result, setResult] = useState<LLMEmbedResponse | null>(null);
  const [fault, setFault] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setRunning(true);
    setFault(null);
    const toastId = toast.loading("Testing embeddings…");
    try {
      const response = await testLlmEmbeddings({ input, model });
      setResult(response);
      toast.update(toastId, {
        render: `Embedding has ${response.dimensions} dimensions.`,
        type: "success",
        isLoading: false,
        autoClose: 4500,
      });
    } catch (caught: unknown) {
      const message =
        caught instanceof Error ? caught.message : "Embedding test failed.";
      setFault(message);
      setResult(null);
      toast.update(toastId, {
        render: message,
        type: "error",
        isLoading: false,
        autoClose: 6000,
      });
    } finally {
      setRunning(false);
    }
  }

  return (
    <form className={`${CARD} grid gap-4`} onSubmit={onSubmit}>
      <div>
        <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
          Test
        </p>
        <h2 className="font-serif text-[1.45rem] font-semibold tracking-tight">
          Embeddings
        </h2>
      </div>
      <label className="grid gap-1.5 text-sm font-semibold">
        Input
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          rows={4}
          className={`${CONTROL} min-h-28 resize-y`}
        />
      </label>
      <button
        type="submit"
        className={PRIMARY_BUTTON}
        disabled={running || disabled || !input.trim()}
      >
        {running ? "Embedding…" : "Run embedding test"}
      </button>
      {fault ? (
        <p className="rounded-control bg-fail/10 px-3.5 py-3 text-sm leading-relaxed text-fail">
          {fault}
        </p>
      ) : null}
      {result ? (
        <div className="rounded-control border border-line bg-sand/60 px-3.5 py-3">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">
            {result.model} · {result.dimensions} dimensions
          </p>
          <p className="mt-2 font-mono text-sm leading-relaxed">
            {result.preview.map((value) => value.toFixed(4)).join(", ")}
            {result.dimensions > result.preview.length ? ", …" : ""}
          </p>
        </div>
      ) : null}
    </form>
  );
}

function OllamaPlaceholder({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="ollama-placeholder-title"
        className="max-w-md rounded-card border border-line/80 bg-paper p-6 shadow-card"
        onClick={(event) => event.stopPropagation()}
      >
        <p className="mb-1 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-cardinal">
          Fallback
        </p>
        <h2
          id="ollama-placeholder-title"
          className="font-serif text-[1.55rem] font-semibold tracking-tight"
        >
          Ollama is a placeholder
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-muted">
          This option is here so the app is not tied to one gateway. The router
          can switch to local Ollama, OpenAI, or Anthropic as a fallback without
          rewriting the checker. Ollama is not wired yet, so the current
          provider stays in place.
        </p>
        <button type="button" className={`${PRIMARY_BUTTON} mt-5`} onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}