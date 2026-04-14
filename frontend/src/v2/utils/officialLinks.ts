// Official pricing / docs pages for each model maker.
// The keys match the `maker` field on EntityCoreV2 — keep in sync with
// the Python FAMILY_PATTERNS / AUTHOR_PREFIX_TO_MAKER tables.

interface OfficialLink {
  pricing: string;
  docs?: string;
}

const LINKS: Record<string, OfficialLink> = {
  Anthropic: {
    pricing: 'https://www.anthropic.com/pricing#api',
    docs: 'https://docs.anthropic.com/en/docs/about-claude/models/overview',
  },
  OpenAI: {
    pricing: 'https://openai.com/api/pricing',
    docs: 'https://platform.openai.com/docs/models',
  },
  Google: {
    pricing: 'https://ai.google.dev/gemini-api/docs/pricing',
    docs: 'https://ai.google.dev/gemini-api/docs/models',
  },
  xAI: {
    pricing: 'https://docs.x.ai/docs/models',
    docs: 'https://docs.x.ai/docs/overview',
  },
  DeepSeek: {
    pricing: 'https://api-docs.deepseek.com/quick_start/pricing',
    docs: 'https://api-docs.deepseek.com',
  },
  'Moonshot AI': {
    pricing: 'https://platform.moonshot.ai/docs/pricing/chat',
    docs: 'https://platform.moonshot.ai/docs',
  },
  Alibaba: {
    pricing: 'https://www.alibabacloud.com/help/en/model-studio/models',
    docs: 'https://www.alibabacloud.com/help/en/model-studio',
  },
  'Z.AI': {
    pricing: 'https://docs.z.ai/guides/overview/pricing',
    docs: 'https://docs.z.ai/',
  },
  MiniMax: {
    pricing: 'https://www.minimax.io/pricing',
    docs: 'https://www.minimax.io/platform_overview',
  },
  Meta: {
    pricing: 'https://www.llama.com/docs/overview',
    docs: 'https://www.llama.com/docs/model-cards-and-prompt-formats',
  },
  Mistral: {
    pricing: 'https://mistral.ai/pricing',
    docs: 'https://docs.mistral.ai/getting-started/models/models_overview/',
  },
  Cohere: {
    pricing: 'https://cohere.com/pricing',
    docs: 'https://docs.cohere.com/docs/models',
  },
  AI21: {
    pricing: 'https://www.ai21.com/pricing',
    docs: 'https://docs.ai21.com/docs/models',
  },
  NVIDIA: {
    pricing: 'https://build.nvidia.com/explore/discover',
    docs: 'https://build.nvidia.com',
  },
  Microsoft: {
    pricing: 'https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/',
    docs: 'https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/models',
  },
  Amazon: {
    pricing: 'https://aws.amazon.com/bedrock/pricing/',
    docs: 'https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html',
  },
  'Black Forest Labs': {
    pricing: 'https://blackforestlabs.ai/pricing/',
    docs: 'https://docs.bfl.ai/',
  },
  'Stability AI': {
    pricing: 'https://platform.stability.ai/pricing',
    docs: 'https://platform.stability.ai/docs/getting-started',
  },
  'Voyage AI': {
    pricing: 'https://docs.voyageai.com/docs/pricing',
    docs: 'https://docs.voyageai.com/docs/embeddings',
  },
  'Jina AI': {
    pricing: 'https://jina.ai/embeddings/',
    docs: 'https://jina.ai/embeddings/',
  },
  AssemblyAI: {
    pricing: 'https://www.assemblyai.com/pricing',
    docs: 'https://www.assemblyai.com/docs',
  },
  Deepgram: {
    pricing: 'https://deepgram.com/pricing',
    docs: 'https://developers.deepgram.com/docs',
  },
  ElevenLabs: {
    pricing: 'https://elevenlabs.io/pricing',
    docs: 'https://elevenlabs.io/docs',
  },
  '01.AI': {
    pricing: 'https://platform.01.ai/docs#pricing',
    docs: 'https://platform.01.ai/docs',
  },
  Baidu: {
    pricing: 'https://cloud.baidu.com/product/wenxinworkshop',
    docs: 'https://cloud.baidu.com/doc/WENXINWORKSHOP/index.html',
  },
  ByteDance: {
    pricing: 'https://www.volcengine.com/product/doubao',
    docs: 'https://www.volcengine.com/docs/82379',
  },
  Tencent: {
    pricing: 'https://cloud.tencent.com/product/hunyuan',
    docs: 'https://cloud.tencent.com/document/product/1729',
  },
  StepFun: {
    pricing: 'https://platform.stepfun.com/docs/pricing',
    docs: 'https://platform.stepfun.com/docs',
  },
  'Deep Cogito': {
    pricing: 'https://www.deepcogito.com/research',
    docs: 'https://www.deepcogito.com/research',
  },
  Perplexity: {
    pricing: 'https://docs.perplexity.ai/guides/pricing',
    docs: 'https://docs.perplexity.ai',
  },
};

export function officialLinkForMaker(maker: string | null | undefined): OfficialLink | null {
  if (!maker) return null;
  return LINKS[maker] ?? null;
}

// Single source of truth — LiteLLM registry JSON (raw on GitHub).
// Used to tell users where our cross-provider data comes from.
export const LITELLM_REGISTRY_URL =
  'https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json';
