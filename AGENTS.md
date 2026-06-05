# AGENTS.md instructions for /Users/a1234/Documents/coding/projects/agent_hpc

如果包缺失，可以自己下载和配置。优先使用 mamba/conda，必要时可以使用镜像站。轻量环境检查、安装、导入测试可以在命令行执行；大规模计算、公开数据验证、真实数据验证必须通过 Slurm。

## 远程服务器工作禁忌与偏好

### 禁忌

- 禁止在登录节点运行重计算任务。
- 禁止把项目、数据、结果放在 home 目录。
- 禁止跳过 Slurm 直接跑长任务。配环境、查版本、轻量 import 测试等小命令可以直接执行。
- 禁止覆盖原始数据。
- 禁止随意删除旧结果，除非用户明确确认。
- 禁止硬编码个人临时路径。
- 禁止猜测软件路径、环境名、参考基因组位置。
- 禁止在未检查 sinfo、squeue、日志的情况下判断任务状态。
- 禁止报错后盲目重跑。
- 禁止不看日志就修改代码。
- 禁止输出无法直接执行的模糊建议。
- 禁止修改主流程之外的无关文件。
- 禁止破坏已有目录结构和命名规范。
- 禁止在未备份的情况下重构核心脚本。
- 禁止把中间文件和最终结果混放。
- 禁止省略版本、参数、输入输出记录。

### 偏好

- 所有正式项目默认放在 `/shared` 下；Ultimate 正式根目录为 `/shared/shen/2026/ultimate`。
- 默认使用较充足计算资源，但不能浪费集群资源。
- 默认使用清晰、可复现、可直接执行的命令。
- 默认先检查环境、路径、输入文件、软件版本。
- 默认先小样本测试，再全量运行。
- 默认保留日志、manifest、参数记录。
- 默认把脚本、日志、结果、临时文件分开放。
- 默认使用 `set -euo pipefail`。
- 默认使用绝对路径或明确的项目根目录变量。
- 默认不动原始数据，只读输入，另存输出。
- 默认先定位错误原因，再给最小修复方案。
- 默认优先短、稳、可验证的方案。
- 默认每一步都能被人工复查。
- 默认输出结果后检查文件是否存在、是否非空、日志是否报错。
- 默认所有重大修改前先说明会改什么。
- Ultimate 平台默认总占用不超过 500G；环境、公共验证数据、缓存、容器和参考资源都计入这个预算。超过预算前必须先审计体积并清理或降级为可选资源。
- 生产级验证优先使用轻量公开数据或已有内部验证数据，不默认下载重型 atlas、大型参考库或大规模容器缓存。
- 容器、conda/mamba 环境、参考基因组、索引、公共数据和验证数据优先复用已有共享资源；不得为每个模块或每个项目重复下载、重复构建同类资源。
- human/mouse 参考基因组、GTF、STAR/HISAT2/BWA/Salmon/Cell Ranger/Cell Ranger ARC/Cell Ranger ATAC/Space Ranger 等参考库和索引必须优先复用已有共享路径；不得在未检查已有资源前重复构建。

## Ultimate Bioinfo Workbench 全局原则

Ultimate 的目标不是单一 scRNA pipeline，而是生产级个人多组学生信分析交付平台。所有模块必须共享统一外壳。

### Ultimate 的实际定位

Ultimate 不是全自动接单、自动报价或自动替用户承诺生物学结论的系统。它的定位是给 Codex 使用的个人多组学生信分析 workbench：用户负责客户沟通、需求判断、报价、解释边界和最终拍板；Codex 负责在用户给出数据路径、样本表、物种、分组、分析模块和需求说明后，使用 Ultimate 进行预检、运行、出图、报告、manifest 和可复现代码交付。

Ultimate 的设计目标是让 Codex “跑起来时有趁手工具”，而不是让平台替代人工判断。所有模块应优先提供稳定 CLI、配置模板、样本表模板、Slurm wrapper、报告模板、统一出图、manifest、复现包和清晰失败原因。

### 半自动接单判断入口

平台需要提供半自动技术判断入口，例如：

```bash
ultimate triage --request config/analysis_request.yaml --output-dir triage/<job_id>
```

`triage` 用于帮助用户做接单前技术判断，但不自动开跑、不自动报价、不自动标记 production。它应输出：

- 数据类型和输入完整性判断。
- 推荐模块和推荐 preset。
- 是否可直接开跑：`ready_to_run`、`needs_metadata`、`needs_dependency`、`needs_license`、`needs_manual_review`。
- 必要的风险提示和解释边界。
- 建议的 `project.yaml`、samplesheet 草稿和 Slurm 命令草稿。
- 中文 `triage_report.md/html`。

`triage` 禁止事项：

- 禁止自动报价。
- 禁止自动启动重计算。
- 禁止把项目自动标成 `production_backend`。
- 禁止凭文件名强行推断客户真实需求。
- 禁止把推断性分析写成确定机制结论。
- 禁止移动、覆盖或改写客户 raw data。

推荐 triage 输出状态：

```text
ready_to_run
needs_metadata
needs_dependency
needs_license
needs_manual_review
not_supported
```

推荐 analysis preset：

```text
basic
standard
tumor
trajectory
communication
velocity
publication
handoff_required
```

- 所有服务器项目路径必须位于 `/shared/shen/2026/ultimate` 或其子目录。
- 不允许重计算任务跑在 login node。
- 大任务必须通过 Slurm。
- 不允许覆盖 raw data。
- 不允许静默失败。
- 不允许把缺失工具、缺失输入、缺失许可证伪装成成功。
- 不允许把 placeholder、stub、demo edge、cluster label、假数据或简化统计伪装成正式生物学结论。
- 每个模块保留自己的分析逻辑，不允许强行套 scRNA 模板。
- 优先复用成熟工具，不重新发明已有算法。
- 每个模块的高级工具若未真正接入，只能标记为 `handoff`、`optional backend` 或 `adapter`，不得写成 fully automatic。
- 所有输出必须可复现，必须记录命令、参数、软件版本、输入路径、输出路径和 Slurm job id。
- 平台存储预算上限为 500G；重型参考库、容器缓存和大型公开数据不得默认纳入核心平台，确需使用时必须独立记录来源、路径、体积和清理策略。
- 容器缓存、环境目录、参考库目录和公共数据目录必须统一规划并可复用；同一版本资源原则上只保留一份，重复资源需要清理或登记为临时例外。
- 如确需新建参考库或索引，必须记录物种、版本、来源、构建命令、构建时间、路径、体积和可复用范围，并优先放入统一 reference 目录供后续模块复用。

### 每个模块必须具备

- `input contract`
- `preflight`
- `demo / smoke test`
- `public` 或 `internal validation plan`
- `run_manifest.json`
- `raw_qc_manifest.json` 或 `module_qc_manifest.json`
- `results/tables/`
- `results/figures/`
- `objects/`
- `reports/report.html`
- `reports/methods.md`
- `logs/`
- `pytest`
- `known limitations`
- `handoff template`

### 每个模块必须显式写入

- `analysis_level`
- `is_demo`
- `is_stub`
- `delivery_allowed`
- `validation_evidence_allowed`
- `non_delivery_reason`

`analysis_level` 只能是：

- `demo_result`
- `smoke_backend`
- `validated_backend`
- `production_backend`

交付规则：

- `demo_result` 和 `smoke_backend` 不允许被当作正式交付。
- `validated_backend` 只代表公开数据或内部验证数据跑通，不等于客户正式交付。
- `production_backend` 必须经过 approval gate，不允许 CLI 直接绕过。
- 任何 demo、stub、placeholder、简化统计、cluster label 或未验证高级工具都不能让 `delivery_allowed=true`。

### 推荐模块目录结构

```text
src/ultimate/modules/<module_name>/
  contract.py
  preflight.py
  demo.py
  validate.py
  run.py
  report.py
  handoff.py
  limitations.py
  tests/
```

### 统一 audit-production 汇总字段

```text
module_name
input_contract_status
preflight_status
demo_smoke_status
public_validation_status
formal_backend_status
report_status
analysis_level
delivery_allowed
known_limitations
next_required_backend
```

## 模块行动边界

第一阶段先保证每个模块不会乱说话，再保证每个模块能跑通，最后才追求高级分析自动化。不要所有模块同时开 full backend。

### 1. bulk RNA-seq (`rnaseq`)

- 支持输入：FASTQ handoff、raw count matrix、TPM/FPKM matrix、Salmon quant、featureCounts table、sample metadata、design table。
- 第一阶段实现：`contract.py`、`preflight.py`、`demo.py`、`validate.py`、`report.py`、`handoff.py`、pytest。
- 必须输出：counts raw/normalized、sample QC、design check、DE results 或 DE-ready handoff、enrichment handoff、PCA、sample correlation heatmap、volcano、top gene heatmap、report、methods、manifest。
- 禁止事项：没有生物学重复时不得给正式 DE 结论；不得用 TPM/FPKM 直接跑 DESeq2；不要立即实现完整 nf-core/rnaseq 自动运行，只写 nf-core/rnaseq handoff templates。

### 2. scRNA-seq (`scrna`)

- 支持输入：10x h5、10x mtx、h5ad、loom handoff、Seurat rds handoff、samplesheet、cell metadata。
- 第一阶段目标：把 scRNA MVP 从 smoke backend 打磨到 validated_backend readiness。
- 必须输出：`objects/scrna_mvp.h5ad`、QC metrics、marker genes、condition DE、cell composition、annotation placeholder、pseudobulk counts/design/feature metadata、basic enrichment、QC violin、PCA、UMAP、composition plot、report、methods、manifest、raw QC manifest。
- 禁止事项：cluster label 不能伪装成 cell type；pseudobulk design-ready 不能伪装成已完成 DESeq2/edgeR；CellChat、inferCNV、SCENIC、velocity 未正式接入时只能作为 handoff。

### 3. scATAC-seq (`scatac`)

- 支持输入：FASTQ handoff、fragments.tsv.gz、fragments index、peak matrix、Cell Ranger ATAC output、ArchR handoff、Signac handoff、h5ad/h5mu。
- 第一阶段只做 matrix-level MVP 和 fragments-level handoff，不承诺完整 peak calling。
- 必须输出：cell QC、fragment QC、peak matrix summary、TSS 或 handoff、FRiP 或 handoff、marker peaks、gene activity handoff、motif enrichment handoff、LSI/UMAP、fragment QC plot、peak accessibility heatmap、object、report、methods、manifest。
- 禁止事项：不得套用 scRNA normalize/log1p/HVG 逻辑；peak accessibility 不能写成 gene expression；gene activity score 是推断值；motif enrichment 不等于 TF 活性实验证明；无 fragments 时不能声称完成 TSS/FRiP/peak calling。

### 4. Multiome (`multiome`)

- 支持输入：10x ARC output、filtered_feature_bc_matrix.h5、RNA count matrix、ATAC peak matrix、fragments.tsv.gz、h5mu、MuData、Seurat multiome handoff、ArchR handoff。
- 第一阶段只做 h5mu/MuData object 和 QC/handoff，不强行实现 full multiVI。
- 必须输出：RNA QC、ATAC QC、barcode overlap、modality consistency、RNA marker handoff、ATAC marker peak handoff、peak-gene link handoff、joint embedding placeholder、modality QC、object、report、methods、manifest。
- 禁止事项：Multiome 不等于简单 scRNA + scATAC 拼接；必须检查 RNA 和 ATAC barcode overlap；peak-gene linkage 是统计关联，不是实验证明；WNN/multiVI 未接入前只能 handoff。

### 5. VDJ / TCR / BCR (`vdj`)

- 支持输入：filtered_contig_annotations.csv、clonotypes.csv、AIRR table、MiXCR output、Cell Ranger VDJ output、scirpy AnnData、immunarch input、paired scRNA metadata。
- 第一阶段用公开 10x VDJ 数据做 validated_backend。
- 必须输出：VDJ QC、clonotype summary、clone expansion、clone sharing、V/J usage、CDR3 length、clone-condition summary、clone size distribution、V gene usage plot、clone sharing heatmap、object、report、methods、manifest。
- 禁止事项：VDJ 分析不以 UMAP 聚类为主流程；clonotype 相同不等于抗原相同；抗原特异性不能自动断言；clone-state association 依赖外部 scRNA metadata，必须标注。

### 6. scDNA-seq / 单细胞基因组 (`scdna`)

- 支持输入：BAM、VCF、cell x mutation matrix、cell x CNV matrix、MissionBio/Tapestri output、amplicon variant table、WGS/WES handoff。
- 第一阶段只做 table/BAM/VCF handoff 和 matrix-ready 输出，不做 full phylogeny。
- 必须输出：coverage QC、variant QC、cell variant matrix、cell VAF matrix、cell CNV matrix、clone summary、mutation cooccurrence、phylogeny input、coverage distribution、VAF heatmap、clone summary plot、report、methods、manifest。
- 禁止事项：scDNA 与 scRNA 完全不同，不能套用表达矩阵分析套路；allele dropout、低覆盖、amplicon bias 必须写入限制；克隆树是模型结果，不是唯一真实进化历史；mutation order 推断必须标注假设。

### 7. mtDNA / 线粒体谱系 (`mtdna`)

- 支持输入：BAM、mtDNA BAM、base count table、variant table、cell x variant VAF matrix、mgatk/MitoTrace/mitoClone2/cellsnp-lite/vireo output。
- 第一阶段优先对接 `/shared/shen/2026/0518` mtDNA 结果，做 internal validated_backend。
- 必须输出：mtDNA depth by cell/position、variant candidates、high-confidence variants、cell variant VAF/alt count matrix、shared variant matrix、lineage input、depth distribution、VAF heatmap、shared variant heatmap、report、methods、manifest。
- 禁止事项：mtDNA lineage 不能套用普通 scRNA marker 逻辑；低深度细胞不能进入 lineage-ready 输出；homopolymer、NUMTs、mapping bias、dropout 必须写入报告；shared variant 不能自动当作真实克隆关系。

### 8. methylation / 单细胞表观遗传 (`methylation`, `scepi`)

- 支持输入：methylation beta matrix、sample metadata、IDAT handoff、scBS-seq output handoff、CUT&Tag/CUT&RUN peak matrix、BED、bigWig handoff。
- 第一阶段只做 matrix-level MVP 和 formal backend handoff，不声称 full single-cell epigenomics。
- 必须输出：feature QC、sample QC、missing value summary、differential regions 或 handoff、promoter/enhancer summary、annotation summary、PCA、sample correlation heatmap、region heatmap、report、methods、manifest。
- 禁止事项：methylation beta matrix、scBS-seq、CUT&Tag、CUT&RUN、scATAC 不能混用同一分析套路；DMR 需要分组和重复数；peak calling 依赖实验类型和 control。

### 9. CITE-seq / ADT (`cite_seq`)

- 支持输入：10x feature-barcode matrix、RNA matrix、ADT matrix、h5mu、Seurat object handoff、cell metadata、antibody panel。
- 第一阶段用 10x public CITE-seq matrix 做 validated_backend。
- 必须输出：ADT QC、antibody panel、ADT normalized matrix、ADT marker summary、RNA-protein consistency、ADT count distribution、ADT heatmap、RNA-protein consistency plot、joint object、report、methods、manifest。
- 禁止事项：ADT 不是全蛋白组；抗体 panel 决定可解释范围；ADT background 必须检查；RNA/protein 不一致不能自动解释为机制。

### 10. 空间转录组 (`spatial`)

- 支持输入：Space Ranger output、filtered_feature_bc_matrix.h5、tissue_positions.csv、scalefactors_json.json、HE image、SpatialData、Xenium/CosMX/MERSCOPE handoff。
- 第一阶段只做 Visium MVP，Xenium/CosMX/MERSCOPE 只做 handoff contract。
- 必须输出：spatial QC、spot metadata、coordinate check、domain summary、spatial marker handoff、deconvolution handoff、spatial neighbors、spatial QC plot、spatial cluster、domain map、object、report、methods、manifest。
- 禁止事项：Visium spot 不是单细胞；Visium、Xenium、CosMX、MERSCOPE 不能强行走同一输入逻辑；deconvolution 依赖 reference，必须写限制；空间通讯是推断，不是实验证明。

### 11. Perturb-seq / CRISPR screen (`perturb_seq`)

- 支持输入：gene expression matrix、guide count matrix、guide assignment table、perturbation design、target gene table、cell metadata、h5ad handoff。
- 第一阶段只做 guide assignment 和 design-ready outputs，不做完整 perturbation model。
- 必须输出：guide QC、guide assignment、perturbation summary、perturbation expression effect、pseudobulk by perturbation、target response、guide distribution、perturbation UMAP placeholder、report、methods、manifest。
- 禁止事项：Perturb-seq 不能当普通 scRNA 加一列 metadata 处理；guide assignment 错误会污染全部结论，必须单独 QC；多 guide 细胞处理策略必须记录；perturbation effect 不能自动写成直接机制。

### 12. HTO / Cell Hashing (`hto_demux`)

- 支持输入：HTO count matrix、antibody capture matrix、cell barcode list、sample-hashtag mapping、10x feature-barcode matrix。
- 第一阶段实现 matrix-level HTO assignment summary，不强行调用 R 后端。
- 必须输出：HTO QC、HTO assignment、sample assignment summary、doublet summary、cell metadata with sample、HTO density、HTO heatmap、report、methods、manifest。
- 禁止事项：HTO 模块只负责 sample assignment，不负责 cell type；negative 不能强行分样本；doublet 阈值必须记录；ambient hashtag 必须提示。

### 13. genotype demultiplexing (`genotype_demux`)

- 支持输入：BAM、barcodes.tsv、VCF、cellsnp-lite/vireo/souporcell/demuxlet/popscle output。
- 第一阶段只做 existing result import + handoff，不自动重跑全部 demux pipeline。
- 必须输出：SNP QC、assignment、doublet summary、sample composition、assignment confidence、cell metadata with genotype、sample assignment barplot、confidence distribution、report、methods、manifest。
- 禁止事项：genotype demux 不能替代 biological replicate design；SNP 覆盖不足时不能强行 assignment；reference VCF 错配必须警示。

### 14. functional state / metabolism (`functional_state`)

- 支持输入：expression matrix、h5ad、bulk expression matrix、single-cell object、GMT、自定义 gene set table、sample/cell metadata。
- 第一阶段只实现 generic signature scoring + overlap check。
- 必须输出：geneset overlap、signature scores、signature by group/cluster、signature correlation、signature heatmap、signature boxplot、report、methods、manifest。
- 禁止事项：signature score 不是代谢通量；药物敏感性预测不能写成临床建议；gene set 来源必须记录；不同评分方法不可直接混比。

### 15. tumor single-cell specialty (`tumor_sc`)

- 支持输入：h5ad/Seurat object、cell type annotation、cluster marker table、tumor/normal metadata、CNV inference result、clinical metadata、therapy/response/relapse grouping。
- 第一阶段只做 summary/handoff，不自动跑 full inferCNV/CopyKAT。
- 必须输出：malignant cell candidates、CNV inference summary、TME composition、immune state scores、myeloid state scores、CAF subtype summary、tumor state markers、therapy response comparison、TME composition plot、tumor state heatmap、report、methods、manifest。
- 禁止事项：tumor_sc 是复合专项，不是一种原始数据类型；malignant calling 不能只靠一个 marker；inferCNV/CopyKAT 是 transcriptome-inferred CNV，不是 DNA CNV；exhaustion score 不是功能实验；survival association 不能写成因果。

### 16. clinical association (`clinical_assoc`)

- 支持输入：sample-level feature matrix、cell proportion table、signature score table、clinical metadata、survival time/status、response group、batch/covariates。
- 第一阶段只做统计-ready 输出和 placeholder KM/Cox，不做真实风险模型自动化。
- 必须输出：clinical QC、merged feature-clinical、group comparison、correlation results、Cox model handoff、risk score placeholder、missingness plot、correlation heatmap、KM placeholder、report、methods、manifest。
- 禁止事项：clinical association 是样本级统计，不是细胞级随便相关；样本量不足时不能构建稳定风险模型；survival analysis 必须有 time/status；correlation 不等于 causation。

### 17. public database mining (`publicdb`)

- 支持输入：GEO matrix、TCGA expression/clinical、GTEx expression、DepMap dependency、HPA table、cached public expression table、cached clinical table。
- 第一阶段只支持 cached public tables + manifest，不自动大规模下载。
- 必须输出：public dataset manifest、sample inclusion、expression matrix summary、clinical table summary、validation results、survival results handoff、public validation boxplot、public survival placeholder、report、methods、manifest。
- 禁止事项：公共数据库必须记录来源、版本、下载时间、筛选规则；GEO metadata 必须人工核对风险；TCGA bulk 验证不能直接证明单细胞机制；外部验证失败不能自动解释成假设错误。

### 18. WGCNA / 共表达网络 (`wgcna`)

- 支持输入：bulk expression matrix、pseudobulk expression matrix、sample metadata、clinical traits、gene annotation。
- 第一阶段只做 WGCNA-ready contract 和 sample/gene QC，正式 WGCNA 可作为 R backend。
- 必须输出：WGCNA input QC、soft threshold handoff、module assignment、module eigengenes、module-trait correlation、hub genes、network export、sample clustering、module-trait heatmap、soft threshold plot、report、methods、manifest。
- 禁止事项：WGCNA 更适合 bulk/pseudobulk，不允许默认对 cell-level sparse matrix 硬跑；样本数太少必须阻断 production_backend；module-trait correlation 是相关，不是机制；hub gene 不是自动靶点。

### 19. single-gene analysis (`single_gene`)

- 支持输入：gene symbol list、bulk expression matrix、single-cell h5ad、cell metadata、clinical metadata、public expression table。
- 第一阶段只做 gene-level report，不做复杂机制推断。
- 必须输出：gene validation、gene expression summary、group comparison、celltype expression、coexpression results、pathway association handoff、clinical association handoff、gene expression boxplot、celltype expression dotplot、coexpression heatmap、report、methods、manifest。
- 禁止事项：单基因表达差异不能直接推出机制；coexpression 不等于 regulation；单基因预后模型稳定性有限，必须警示；public validation 依赖队列质量。

### 20. method_tools / interactive delivery (`method_tools`)

- 支持输入：h5ad、h5mu、SpatialData、Seurat object handoff、figures、tables、manifest、report。
- 第一阶段只做 static delivery manifest + cellxgene compatibility check + table/figure index。
- 必须输出：cellxgene-ready object 或 compatibility report、Vitessce config handoff、figure index、table index、sensitive metadata scan、methods、delivery manifest、report。
- 禁止事项：大对象不重复拷贝，优先 reference-first；交互式浏览器只是展示，不改变分析结论；公开交付前必须脱敏 metadata；delivery package 必须记录软件版本和路径。

### 21. proteomics / metabolomics (`proteomics`)

- 支持输入：MaxQuant 表、Proteome Discoverer 表、通用 abundance table、metabolomics peak table、sample metadata。
- 第一阶段做 matrix-level QC、差异分析 handoff、PCA/热图/火山图、富集和 PPI handoff。
- 必须输出：feature QC、sample QC、normalized abundance、design check、differential table 或 handoff、enrichment/PPI handoff、PCA、correlation heatmap、volcano、feature heatmap、report、methods、manifest。
- 禁止事项：蛋白组/代谢组不能套 bulk RNA-seq 统计假设；缺失值处理、归一化、批次效应、OPLS-DA 都必须记录方法和限制。

## 参考 GitHub / 官方工程清单

这些项目是优先参考、适配或写 handoff template 的来源。未真正接入、未安装、未验证前，只能写作参考工程、可选后端或 handoff，不得写成 Ultimate 已经 fully automatic 支持。

### bulk RNA-seq

- nf-core/rnaseq: https://github.com/nf-core/rnaseq
- DESeq2: https://github.com/thelovelab/DESeq2
- edgeR: https://bioconductor.org/packages/release/bioc/html/edgeR.html
- limma: https://bioconductor.org/packages/release/bioc/html/limma.html
- clusterProfiler: https://github.com/YuLab-SMU/clusterProfiler
- GSEApy: https://github.com/zqfang/GSEApy
- MultiQC: https://github.com/MultiQC/MultiQC

### scRNA-seq

- scanpy: https://github.com/scverse/scanpy
- anndata: https://github.com/scverse/anndata
- Seurat: https://github.com/satijalab/seurat
- scrublet: https://github.com/swolock/scrublet
- SoupX: https://github.com/constantAmateur/SoupX
- celltypist: https://github.com/Teichlab/celltypist
- scvi-tools: https://github.com/scverse/scvi-tools
- nf-core/scrnaseq: https://github.com/nf-core/scrnaseq
- bollito: https://github.com/cnio-bu/bollito

### scATAC-seq

- ArchR: https://github.com/GreenleafLab/ArchR
- Signac: https://github.com/stuart-lab/signac
- SnapATAC2: https://github.com/scverse/SnapATAC2
- chromVAR: https://github.com/GreenleafLab/chromVAR
- MACS: https://github.com/macs3-project/MACS
- bedtools: https://github.com/arq5x/bedtools2
- Cell Ranger ATAC: https://www.10xgenomics.com/support/software/cell-ranger-atac

### Multiome

- muon: https://github.com/scverse/muon
- mudata: https://github.com/scverse/mudata
- Seurat WNN: https://github.com/satijalab/seurat
- Signac: https://github.com/stuart-lab/signac
- ArchR: https://github.com/GreenleafLab/ArchR
- scvi-tools / multiVI: https://github.com/scverse/scvi-tools
- SnapATAC2: https://github.com/scverse/SnapATAC2
- Cell Ranger ARC: https://www.10xgenomics.com/support/software/cell-ranger-arc

### VDJ / TCR / BCR

- scirpy: https://github.com/scverse/scirpy
- immunarch: https://github.com/immunomind/immunarch
- MiXCR: https://github.com/milaboratory/mixcr
- nf-core/airrflow: https://github.com/nf-core/airrflow
- tcrdist3: https://github.com/kmayerb/tcrdist3
- Cell Ranger VDJ: https://www.10xgenomics.com/support/software/cell-ranger

### scDNA-seq / 单细胞基因组

- MissionBio mosaic: https://github.com/MissionBio/mosaic
- nf-core/sarek: https://github.com/nf-core/sarek
- GATK: https://github.com/broadinstitute/gatk
- bcftools: https://github.com/samtools/bcftools
- samtools: https://github.com/samtools/samtools
- SiCloneFit: https://github.com/compbio-mallory/SiCloneFit
- SPhyR: https://github.com/raphael-group/SPhyR
- PhISCS: https://github.com/elkebir-group/PhISCS

### mtDNA / 线粒体谱系

- MitoTrace: https://github.com/LareauCA/MitoTrace
- mitoClone: https://github.com/veltenlab/mitoClone
- mitoClone2: https://github.com/caleblareau/mitoClone2
- cellsnp-lite: https://github.com/single-cell-genetics/cellsnp-lite
- vireo: https://github.com/single-cell-genetics/vireo
- samtools: https://github.com/samtools/samtools
- pysam: https://github.com/pysam-developers/pysam

### methylation / single-cell epigenomics

- minfi: https://bioconductor.org/packages/release/bioc/html/minfi.html
- ChAMP: https://github.com/YuanTian1991/ChAMP
- methylKit: https://github.com/al2na/methylKit
- MACS: https://github.com/macs3-project/MACS
- deepTools: https://github.com/deeptools/deepTools
- bedtools: https://github.com/arq5x/bedtools2
- Signac: https://github.com/stuart-lab/signac
- ArchR: https://github.com/GreenleafLab/ArchR

### CITE-seq / ADT

- Seurat: https://github.com/satijalab/seurat
- muon: https://github.com/scverse/muon
- mudata: https://github.com/scverse/mudata
- scvi-tools / totalVI: https://github.com/scverse/scvi-tools
- DSB: https://github.com/niaid/dsb

### Spatial transcriptomics

- squidpy: https://github.com/scverse/squidpy
- spatialdata: https://github.com/scverse/spatialdata
- spatialdata-io: https://github.com/scverse/spatialdata-io
- sopa: https://github.com/gustaveroussy/sopa
- nf-core/sopa: https://github.com/nf-core/sopa
- Giotto: https://github.com/giottosuite/Giotto
- stLearn: https://github.com/BiomedicalMachineLearning/stLearn
- Space Ranger: https://www.10xgenomics.com/support/software/space-ranger

### Perturb-seq / CRISPR screen

- pertpy: https://github.com/scverse/pertpy
- Seurat / Mixscape: https://github.com/satijalab/seurat
- SCEPTRE: https://github.com/Katsevich-Lab/sceptre
- scanpy: https://github.com/scverse/scanpy

### HTO / Cell Hashing

- Seurat HTODemux: https://github.com/satijalab/seurat
- DropletUtils: https://bioconductor.org/packages/release/bioc/html/DropletUtils.html
- MULTI-seq: https://github.com/chris-mcginnis-ucsf/MULTI-seq
- hashsolo: https://github.com/calico/solo

### Genotype demultiplexing

- cellsnp-lite: https://github.com/single-cell-genetics/cellsnp-lite
- vireo: https://github.com/single-cell-genetics/vireo
- souporcell: https://github.com/wheaton5/souporcell
- demuxlet: https://github.com/statgen/demuxlet
- popscle: https://github.com/statgen/popscle

### functional state / metabolism

- decoupler-py: https://github.com/saezlab/decoupler-py
- GSVA: https://github.com/rcastelo/GSVA
- AUCell: https://github.com/aertslab/AUCell
- UCell: https://github.com/carmonalab/UCell
- GSEApy: https://github.com/zqfang/GSEApy
- PROGENy: https://github.com/saezlab/progeny
- DoRothEA: https://github.com/saezlab/dorothea

### tumor single-cell specialty

- inferCNV: https://github.com/broadinstitute/infercnv
- CopyKAT: https://github.com/navinlabcode/copykat
- CellChat: https://github.com/sqjin/CellChat
- LIANA: https://github.com/saezlab/liana-py
- NicheNet: https://github.com/saeyslab/nichenetr
- decoupler-py: https://github.com/saezlab/decoupler-py

### clinical association

- survival: https://github.com/therneau/survival
- survminer: https://github.com/kassambara/survminer
- lifelines: https://github.com/CamDavidsonPilon/lifelines
- statsmodels: https://github.com/statsmodels/statsmodels
- scikit-learn: https://github.com/scikit-learn/scikit-learn

### public database mining

- GEOquery: https://bioconductor.org/packages/release/bioc/html/GEOquery.html
- TCGAbiolinks: https://github.com/BioinformaticsFMRP/TCGAbiolinks
- UCSC Xena: https://xenabrowser.net/
- cBioPortal: https://github.com/cBioPortal/cbioportal
- DepMap: https://depmap.org/portal/
- pandas: https://github.com/pandas-dev/pandas

### WGCNA / 共表达网络

- WGCNA: https://horvath.genetics.ucla.edu/html/CoexpressionNetwork/Rpackages/WGCNA/
- hdWGCNA: https://github.com/smorabit/hdWGCNA
- igraph: https://github.com/igraph/igraph
- networkx: https://github.com/networkx/networkx

### single-gene analysis

- scanpy: https://github.com/scverse/scanpy
- Seurat: https://github.com/satijalab/seurat
- GSEApy: https://github.com/zqfang/GSEApy
- clusterProfiler: https://github.com/YuLab-SMU/clusterProfiler
- TCGAbiolinks: https://github.com/BioinformaticsFMRP/TCGAbiolinks

### method_tools / interactive delivery

- cellxgene: https://github.com/chanzuckerberg/cellxgene
- Vitessce: https://github.com/vitessce/vitessce
- easy-vitessce: https://github.com/vitessce/easy-vitessce
- Quarto CLI: https://github.com/quarto-dev/quarto-cli
- Jupyter Book: https://github.com/jupyter-book/jupyter-book
- Shiny: https://github.com/rstudio/shiny
- Dash: https://github.com/plotly/dash

## 并行执行策略

大规模任务可以拆分给子 agent，但必须由主线统一接口、统一复核、统一测试、统一合并。

- 主线负责：统一外壳、approval gate、manifest schema、module maturity table、CLI/audit/report 接入、最终验收。
- Worker A：`rnaseq`、`methylation`、`proteomics`、`publicdb`、`clinical_assoc`、`wgcna`、`single_gene`。
- Worker B：`scrna`、`functional_state`、`tumor_sc`、`method_tools`。
- Worker C：`scatac`、`multiome`、`vdj`、`cite_seq`、`spatial`、`scepi`。
- Worker D：`scdna`、`mtdna`、`perturb_seq`、`hto_demux`、`genotype_demux`。
- Worker E：pytest、README、Slurm 脚本、audit-production、GitHub 同步复核。

并行时每个 worker 只改自己拥有的模块目录和对应测试。共享核心文件只由主线修改，避免冲突。所有 worker 输出必须由主线复核后才能合并。

## Git 和交付收口

- 大规模修改优先开独立工作树或 `codex/` 前缀分支。
- 不提交生成图、运行产物、大数据、conda 缓存、远端验证结果快照。
- 只提交源码、模板、Slurm 脚本、环境文件、测试、README/文档。
- 提交前必须检查 `git status`，确认无误后再 commit/push。
- README 必须说明哪些模块是 `demo_result`、`smoke_backend`、`validated_backend`、`production_backend`，不得夸大成熟度。
