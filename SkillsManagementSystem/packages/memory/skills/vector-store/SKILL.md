---
name: vector-store
description: Integrate vector databases (Chroma, Qdrant) for semantic memory retrieval in AI agents. Use when implementing vector search, embeddings storage, semantic retrieval, or RAG for agent memory.
---

# Vector Store Integration

Integrate vector databases for semantic memory retrieval in AI agents. Supports Chroma (local, lightweight) and Qdrant (production, scalable).

## Trigger

- "vector store"
- "Chroma"
- "Qdrant"
- "vector database"
- "embedding search"
- "semantic retrieval"
- "RAG memory"

## Engine Selection

### Chroma (Recommended for local dev)
- Zero setup, runs in-process or as local server
- Built-in embedding functions
- Simple API
- SQLite + HNSW index
- Good for: development, single-user, < 100K documents

### Qdrant (Recommended for production)
- High-performance Rust backend
- gRPC API for low latency
- Rich filtering (payload + vector)
- Horizontal scaling
- Good for: production, multi-user, > 100K documents

## Architecture

```
New Memory Entry
      │
      ▼
Embedding Generator (text → vector)
      │
      ├─→ Vector Store (Chroma/Qdrant)
      │   └─→ Semantic search index
      │
      └─→ SQLite (metadata, full details)
          └─→ Keyword search index

Retrieval:
  Query → Hybrid Search → Merge + Rerank → Results
              │
              ├─→ Vector Search (semantic similarity)
              └─→ Keyword Search (exact + fuzzy match)
```

## Chroma Integration

```typescript
import { ChromaClient } from "chromadb";

class ChromaMemoryStore {
  private client: ChromaClient;
  private collection: Collection;

  async initialize(): Promise<void> {
    this.client = new ChromaClient({
      path: "./data/chroma",  // Persist to disk
    });

    this.collection = await this.client.getOrCreateCollection({
      name: "agent-memories",
      metadata: { "hnsw:space": "cosine" },
    });
  }

  async addMemory(memory: MemoryEntry): Promise<void> {
    await this.collection.add({
      ids: [memory.id],
      embeddings: [memory.embedding],  // pre-computed embedding
      metadatas: [{
        type: memory.type,
        timestamp: memory.timestamp,
        importance: memory.importance,
        tags: memory.tags.join(","),
        summary: memory.summary,
      }],
      documents: [memory.summary],  // For built-in embedding if needed
    });
  }

  async searchSimilar(
    query: string,
    queryEmbedding: number[],
    options: {
      limit?: number;
      typeFilter?: MemoryType[];
      importanceMin?: number;
    } = {}
  ): Promise<VectorSearchResult[]> {
    const where: any = {};

    if (options.typeFilter?.length) {
      where.type = { $in: options.typeFilter };
    }
    if (options.importanceMin) {
      where.importance = { $gte: options.importanceMin };
    }

    const results = await this.collection.query({
      queryEmbeddings: [queryEmbedding],
      nResults: options.limit || 10,
      where: Object.keys(where).length > 0 ? where : undefined,
    });

    return formatResults(results);
  }

  async deleteMemory(id: string): Promise<void> {
    await this.collection.delete({ ids: [id] });
  }

  async updateMetadata(
    id: string,
    metadata: Record<string, any>
  ): Promise<void> {
    await this.collection.update({
      ids: [id],
      metadatas: [metadata],
    });
  }
}
```

## Qdrant Integration

```typescript
import { QdrantClient } from "@qdrant/js-client-rest";

class QdrantMemoryStore {
  private client: QdrantClient;
  private collectionName = "agent-memories";

  async initialize(): Promise<void> {
    this.client = new QdrantClient({
      url: process.env.QDRANT_URL || "http://localhost:6333",
      // For cloud: apiKey: process.env.QDRANT_API_KEY,
    });

    // Create collection if not exists
    const collections = await this.client.getCollections();
    if (!collections.collections.find(c => c.name === this.collectionName)) {
      await this.client.createCollection(this.collectionName, {
        vectors: {
          size: 1536,  // Embedding dimension (depends on model)
          distance: "Cosine",
        },
        // Enable quantization for memory efficiency
        quantization_config: {
          scalar: {
            type: "int8",
            quantile: 0.99,
          },
        },
      });

      // Create payload indexes for filtering
      await this.client.createPayloadIndex(this.collectionName, {
        field_name: "type",
        field_schema: "keyword",
      });
      await this.client.createPayloadIndex(this.collectionName, {
        field_name: "importance",
        field_schema: "float",
      });
      await this.client.createPayloadIndex(this.collectionName, {
        field_name: "timestamp",
        field_schema: "integer",
      });
    }
  }

  async addMemory(memory: MemoryEntry): Promise<void> {
    await this.client.upsert(this.collectionName, {
      wait: true,
      points: [{
        id: memory.id,
        vector: memory.embedding,
        payload: {
          type: memory.type,
          timestamp: memory.timestamp,
          importance: memory.importance,
          tags: memory.tags,
          summary: memory.summary,
          emotional_valence: memory.emotionalValence,
        },
      }],
    });
  }

  async searchSimilar(
    queryEmbedding: number[],
    options: {
      limit?: number;
      typeFilter?: MemoryType[];
      importanceMin?: number;
      timeRange?: { start: number; end: number };
    } = {}
  ): Promise<VectorSearchResult[]> {
    const must: any[] = [];

    if (options.typeFilter?.length) {
      must.push({
        key: "type",
        match: { any: options.typeFilter },
      });
    }
    if (options.importanceMin) {
      must.push({
        key: "importance",
        range: { gte: options.importanceMin },
      });
    }
    if (options.timeRange) {
      must.push({
        key: "timestamp",
        range: {
          gte: options.timeRange.start,
          lte: options.timeRange.end,
        },
      });
    }

    const results = await this.client.search(this.collectionName, {
      vector: queryEmbedding,
      limit: options.limit || 10,
      filter: must.length > 0 ? { must } : undefined,
      with_payload: true,
      score_threshold: 0.5,  // Minimum similarity
    });

    return results.map(r => ({
      id: String(r.id),
      score: r.score,
      payload: r.payload as any,
    }));
  }

  // Batch operations for efficiency
  async addMemoriesBatch(memories: MemoryEntry[]): Promise<void> {
    const points = memories.map(m => ({
      id: m.id,
      vector: m.embedding,
      payload: {
        type: m.type,
        timestamp: m.timestamp,
        importance: m.importance,
        tags: m.tags,
        summary: m.summary,
        emotional_valence: m.emotionalValence,
      },
    }));

    await this.client.upsert(this.collectionName, {
      wait: true,
      points,
    });
  }
}
```

## Embedding Generation

```typescript
interface EmbeddingProvider {
  generate(texts: string[]): Promise<number[][]>;
  dimension: number;
}

// Option 1: Local with transformers.js (free, offline)
class LocalEmbeddingProvider implements EmbeddingProvider {
  dimension = 384; // all-MiniLM-L6-v2

  async generate(texts: string[]): Promise<number[][]> {
    const { pipeline } = await import("@xenova/transformers");
    const extractor = await pipeline("feature-extraction", "Xenova/all-MiniLM-L6-v2");
    const outputs = await extractor(texts, { pooling: "mean", normalize: true });
    return outputs.tolist();
  }
}

// Option 2: DeepSeek embeddings (via API)
class DeepSeekEmbeddingProvider implements EmbeddingProvider {
  dimension = 1536;

  async generate(texts: string[]): Promise<number[][]> {
    const response = await fetch("https://api.deepseek.com/v1/embeddings", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${process.env.DEEPSEEK_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "deepseek-embedding",
        input: texts,
      }),
    });
    const data = await response.json();
    return data.data.map((d: any) => d.embedding);
  }
}
```

## Hybrid Search

Combine vector and keyword search for better results:

```typescript
async function hybridSearch(
  query: string,
  vectorStore: VectorStore,
  sqliteDb: SQLiteDB,
  limit: number = 10
): Promise<RankedResult[]> {
  // Parallel search
  const [vectorResults, keywordResults] = await Promise.all([
    vectorStore.searchSimilar(await embed(query), { limit: limit * 2 }),
    sqliteDb.keywordSearch(query, { limit: limit * 2 }),
  ]);

  // Merge with reciprocal rank fusion
  return reciprocalRankFusion(vectorResults, keywordResults, limit);
}

function reciprocalRankFusion(
  vectorResults: SearchResult[],
  keywordResults: SearchResult[],
  k: number = 60
): RankedResult[] {
  const scores = new Map<string, number>();

  for (const [rank, result] of vectorResults.entries()) {
    scores.set(result.id, (scores.get(result.id) || 0) + 1 / (k + rank));
  }
  for (const [rank, result] of keywordResults.entries()) {
    scores.set(result.id, (scores.get(result.id) || 0) + 1 / (k + rank));
  }

  return Array.from(scores.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([id, score]) => ({ id, score }));
}
```
