# singlecell_workbench 工作简报

更新时间：2026-04-17

## 1. 项目当前状态

`singlecell_workbench` 已完成可复跑、可测试、可交接的 CLI-first 单细胞分析骨架，当前项目根目录为：

- 本地：`/Users/a1234/Documents/coding/projects/agent_hpc/singlecell_workbench`
- 服务器：`/shared/shen/2026/singlecell_workbench`

当前流程支持：

- 10x `filtered_feature_bc_matrix.h5`
- 10x `matrix.mtx` / `matrix.mtx.gz` 目录
- 自动识别单模态 / 多模态并导出 `h5ad` 或 `h5mu`
- `obs` / `var` / `layers` / `obsm` / `uns` schema 校验与修复建议
- QC：`scanpy.pp.calculate_qc_metrics`，并集成 SOLO / SCAR 的可选执行路径
- annotation：优先 `scArches + scANVI`，fallback 到 `CellTypist`
- stats：`sample x cell_type x condition` 汇总，以及 `decoupler` pathway / TF 活性分析
- HTML report、methods draft、CLI、config、测试、README、example notebook

## 2. 已完成内容

### 2.1 核心流程

- 已完成 `ingest / qc / annotation / stats / reports` 五个模块
- 已完成最小示例数据生成与全流程跑通
- 已完成 `run_manifest.json` 作为交接主清单

### 2.2 环境与依赖

- 服务器环境已配置为：
  - `/shared/shen/2026/singlecell_workbench/.conda/envs/scw-py311`
- 环境安装脚本：
  - `01_tools/setup_server_env.sh`
- 环境定义文件：
  - `envs/environment.server.yml`

### 2.3 decoupler 修复

- 已确认旧 conda `decoupler 1.5.0` 与当前 `numba` 组合不兼容
- 已切换到 pip 安装 `decoupler 2.1.6`
- `stats` 模块已兼容：
  - `runner: mlm`
  - legacy `runner: run_mlm`
- 已真实跑通 `mt.mlm` 生成 `pathway_activity.csv` / `tf_activity.csv`

### 2.4 官方先验资源

已新增 `fetch-priors` 命令，可冻结官方 pathway / TF network：

```bash
python -m singlecell_workbench fetch-priors \
  --output-dir resources/priors/human_academic \
  --organism human \
  --license academic
```

当前服务器上已生成一套真实快照：

- `resources/priors/human_academic/progeny.tsv`
- `resources/priors/human_academic/collectri.tsv`
- `resources/priors/human_academic/manifest.json`
- `resources/priors/human_academic/stats_config.yaml`

其中：

- `PROGENy`：6463 行
- `CollecTRI`：42990 行

## 3. 验证结果

### 3.1 本地验证

- 当前本地测试结果：`17 passed, 1 skipped`
- 已覆盖：
  - CLI
  - config 路径解析
  - priors 导出
  - ingest
  - qc
  - annotation
  - stats
  - reports
  - pipeline

### 3.2 服务器验证

已确认以下内容可用：

- 环境安装脚本可成功刷新服务器环境
- `decoupler 2.1.6` 可在服务器环境中导入并运行 `mlm`
- `fetch-priors` 已真实生成官方 `PROGENy` / `CollecTRI` 快照
- `stats.run_statistics` 已真实生成：
  - `pathway_activity.csv`
  - `tf_activity.csv`

备注：

- 服务器上的全量 `pytest` 曾受到历史残留子进程影响，已通过定向清理和功能级集成验证确认本轮新增功能可用

## 4. 当前默认使用方式

### 4.1 环境激活

```bash
cd /shared/shen/2026/singlecell_workbench
source /share/home/nshen/miniconda3/etc/profile.d/conda.sh
conda activate /shared/shen/2026/singlecell_workbench/.conda/envs/scw-py311
```

### 4.2 获取官方先验

```bash
python -m singlecell_workbench fetch-priors \
  --output-dir resources/priors/human_academic \
  --organism human \
  --license academic
```

### 4.3 运行真实数据

1. 从 `config/default.yaml` 复制一份运行配置
2. 替换 `samples` 为真实 10x 输入
3. 保留 `stats.decoupler.pathway_network` / `tf_network` 指向 `resources/priors/human_academic`
4. 运行：

```bash
python -m singlecell_workbench run --config config/project_run.yaml
```

## 5. 当前已知事项

- `mudata` 在服务器环境中会产生 `FutureWarning`，但当前不影响流程完成
- annotation 模块若未提供参考模型或模型配置，会按设计进入 fallback / placeholder 路径，并在 manifest 中明确记录原因
- `decoupler` 现在已可用，但真实分析仍依赖你提供合适的 pathway / TF network 与目标物种

## 6. 建议下一步

建议按以下顺序继续：

1. 新建 `config/project_run.yaml`
2. 接入真实样本路径
3. 复用现有 `resources/priors/human_academic/` 先验
4. 先跑一轮小样本或 1-2 个 sample 的 smoke run
5. 再扩展到完整项目

如果后续要正式交给别人，优先一起交付：

- `config/project_run.yaml`
- `run_manifest.json`
- final `h5ad` / `h5mu`
- `report.html`
- `methods.md`

