# Internal implementation contract

Base URL `/api`. JSON keys are snake_case. All identifiers are UUID strings. Errors use FastAPI `detail`. API local port 8000, frontend 3000.

Repository object: `{id,name,source_url,status,error,file_count,chunk_count,languages,created_at,indexed_at,embedding_provider}`. Status `queued|cloning|parsing|embedding|indexing|ready|failed`. Job: `{id,repository_id,kind,status,stage,progress,error,created_at,finished_at}`.

- `GET /health`: database/jobs/providers/sandbox availability.
- `GET /settings`: public provider/mode/limits configuration only.
- `GET /repositories` → repository array.
- `POST /repositories` body `{url}` → repository (queued).
- `POST /repositories/demo` → repository from bundled demo (queued).
- `POST /repositories/upload` multipart `file` → repository (queued).
- `GET /repositories/{id}` → repository.
- `POST /repositories/{id}/index` → job.
- `GET /repositories/{id}/status` → `{repository,job}`.
- `GET /repositories/{id}/files` → array `{path,language,line_count,size_bytes}`.
- `GET /repositories/{id}/files/{path:path}` → `{path,language,content,line_count,symbols:[{name,type,start_line,end_line}]}`.
- `POST /repositories/{id}/query` body `{question,strategy?:"hybrid_rerank",conversation_id?:string}` → `{answer,citations:[{chunk_id,file_path,symbol_name,start_line,end_line,content,score}],retrieval:[same],metrics:{retrieval_ms,reranking_ms,llm_ms,total_ms,retrieved_chunks,model,input_tokens,output_tokens,estimated_cost},conversation_id,mode}`.
- `GET /repositories/{id}/conversations` → array of conversations with messages.
- `GET /repositories/{id}/dependencies` → `{nodes:[{id,path,language}],edges:[{source,target,kind}],limitations}`.
- `GET /repositories/{id}/impact?path=...` → `{path,affected_files,dependencies,explanation}`.
- `POST /repositories/{id}/agent-runs` body `{task,max_steps?:12}` → run (queued).
- `GET /repositories/{id}/agent-runs` → run array.
- `GET /agent-runs/{id}` → `{id,repository_id,task,status,summary,error,steps:[{tool,arguments,result,duration_ms,success,summary}],patch:{diff,files:[{path,before,after,original_hash}],explanation,risks}|null,test_results:[],created_at}`; statuses `queued|running|awaiting_approval|completed|approved|rejected|failed`.
- `POST /agent-runs/{id}/approve` and `/reject` → run. Approval applies exact staged patch to managed copy, invalidates/reindexes metadata.
- `GET /repositories/{id}/evaluation-dataset` → `{id,name,cases:[{question,expected_file,expected_symbol,expected_answer_keywords}]}`.
- `POST /repositories/{id}/evaluations` body optional `{cases:[...],k?:5}` → evaluation run queued.
- `GET /repositories/{id}/evaluations` → run array.
- `GET /evaluations/{id}` → `{id,repository_id,status,error,created_at,metrics:[{strategy,recall_at_k,mrr,avg_latency_ms,avg_retrieved_chunks,answer_keyword_coverage,citation_validity,input_tokens,output_tokens,estimated_cost}],results:[...]}`.

## Python interfaces

Root owns configuration/models/jobs/API/parsing/ingestion/providers/retrieval/dependencies. Agent module owns `agents.py`, `sandbox.py`, `evaluations.py`, related tests. Frontend module owns frontend entire tree. Docs module owns README, Compose/Dockerfiles/scripts/demo and prose docs except this contract, plan and development log.

`app.db.SessionLocal`: SQLAlchemy session factory. `app.config.settings`: settings singleton. `app.models` exposes Repository (root_path), RepositoryFile (path, content, language), CodeChunk (file_path, symbol_name, symbol_type, start_line, end_line, content, embedding), AgentRun (task,status,summary,error,patch JSON,test_results JSON), AgentStep (run_id,tool,arguments JSON,result JSON,duration_ms,success,summary), EvaluationDataset (name,cases JSON), EvaluationRun (status,error,metrics JSON,results JSON). All include id/repository_id where relevant/created_at.

`app.retrieval.retrieve(session, repository_id, question, strategy='hybrid_rerank', k=8)` → `(list[dict citation],dict timing)`; `app.retrieval.answer_question(session, repository_id, question, strategy='hybrid_rerank',conversation_id=None)` → query response. `app.dependencies.graph(session, repository_id)` / `impact(session,repository_id,path)` → API dicts. `app.jobs.submit(kind, entity_id)` queues `index`, `agent`, `evaluation`. Agent `execute_agent(run_id)`; evaluation `execute_evaluation(run_id)` use own SessionLocal and persist statuses. `app.agents.approve_run(session,run)` / `reject_run(session,run)` and `serialize_run(session,run)` provide API results. Sandbox `DockerSandbox.available()` and `.run(root_path,command)` produce structured real result. `settings.data_dir` is pathlib Path; `settings.sandbox_enabled`, `settings.sandbox_timeout`, `settings.llm_provider`, `settings.llm_model`, `settings.openai_api_key`, `settings.openai_base_url`, `settings.agent_max_steps`.
