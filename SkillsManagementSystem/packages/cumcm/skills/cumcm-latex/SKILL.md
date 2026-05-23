---
name: cumcm-latex
description: CUMCM LaTeX 排版技能。涵盖：LaTeX 文档生成、公式排版、三线表、图表插入、交叉引用、参考文献管理。兼容 ctexart / cumcmthesis 模板、TeX Live、Overleaf。触发：用户提到"LaTeX""排版""tex""公式""模板""编译"等。
---

# CUMCM LaTeX 排版

## 核心原则

**排版的目标是让评审者轻松阅读**，而非展示 LaTeX 技巧。使用 CUMCM 标准模板，确保可通过编译。

## 推荐模板

### 国赛专用：cumcmthesis

```latex
% !TeX program = xelatex
\documentclass[UTF8]{cumcmthesis}
```

学校通常提供 `cumcmthesis.cls`。如果没有，使用 `ctexart` + 手动配置：

```latex
% !TeX program = xelatex
\documentclass[UTF8,a4paper,12pt]{ctexart}
```

## 基本模板

```latex
% !TeX program = xelatex
\documentclass[UTF8,a4paper,12pt]{ctexart}

% === 页面设置 ===
\usepackage[top=2.5cm, bottom=2.5cm, left=3.2cm, right=3.2cm]{geometry}

% === 数学 ===
\usepackage{amsmath, amssymb, amsthm}
\usepackage{bm}          % 粗体希腊字母

% === 图表 ===
\usepackage{graphicx}
\usepackage{booktabs}    % 三线表
\usepackage{caption}
\usepackage{subcaption}  % 子图
\usepackage{float}       % [H] 强制位置

% === 超链接 ===
\usepackage[hidelinks]{hyperref}

% === 标题格式 ===
\ctexset{
    section/format = {\Large\bfseries},
    subsection/format = {\large\bfseries},
}

% === 行间距 ===
\usepackage{setspace}
\onehalfspacing

% === 参考文献（可选）===
\usepackage[numbers,sort&compress]{natbib}

\title{\heiti\zihao{2} 全国大学生数学建模竞赛论文}
\author{队伍编号：XXXXXX}
\date{}

\begin{document}

\maketitle

\begin{center}
\zihao{4}
\begin{tabular}{ll}
\textbf{队员一}：XXX & 专业：XXX \\
\textbf{队员二}：XXX & 专业：XXX \\
\textbf{队员三}：XXX & 专业：XXX \\
\end{tabular}
\end{center}

% === 正文 ===
\section{问题重述}
...

\end{document}
```

## 常用公式排版

### 基本公式环境

```latex
% 行内公式
设 $x_i$ 为第 $i$ 个样本的观测值。

% 行间公式（无编号）
\[
y = \sum_{i=1}^{n} w_i x_i
\]

% 行间公式（有编号）
\begin{equation}\label{eq:main}
y = \beta_0 + \beta_1 x_1 + \beta_2 x_2 + \varepsilon
\end{equation}

% 多行对齐
\begin{align}
y &= a + b \cdot x + c \cdot x^2 \label{eq:quad} \\
R^2 &= 1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y})^2} \label{eq:r2}
\end{align}

% 多行公式（一个编号）
\begin{equation}\label{eq:split}
\begin{split}
f(x) &= a_0 + a_1 x + a_2 x^2 + a_3 x^3 \\
     &\quad + a_4 x^4 + a_5 x^5
\end{split}
\end{equation}

% 分段函数
\begin{equation}
f(x) = \begin{cases}
x^2, & x \geq 0 \\
0,   & x < 0
\end{cases}
\end{equation}
```

### 矩阵

```latex
% 方括号矩阵
\[
A = \begin{bmatrix}
a_{11} & a_{12} & \cdots & a_{1n} \\
a_{21} & a_{22} & \cdots & a_{2n} \\
\vdots & \vdots & \ddots & \vdots \\
a_{m1} & a_{m2} & \cdots & a_{mn}
\end{bmatrix}
\]

% 行内小矩阵
设 $X = (x_1, x_2, \ldots, x_n)^T$ 为特征向量。
```

### 常用符号

```latex
% 希腊字母加粗
\bm{\alpha}, \bm{\beta}, \bm{\theta}

% 求和/求积
\sum_{i=1}^{n}, \prod_{j=1}^{m}

% 偏导
\frac{\partial f}{\partial x}

% 范数
\| \cdot \|_2, \| \cdot \|_{\infty}

% 条件概率
P(A \mid B)

% 转置
X^T

% 近似
\approx, \sim

% 渐近
\to, \rightarrow

% 最大化/最小化
\max_{x}, \min_{x}
\mathop{\arg\max}_{x}, \mathop{\arg\min}_{x}
```

## 三线表 (booktabs)

```latex
% 基本三线表
\begin{table}[H]
\centering
\caption{表标题在上方}
\label{tab:example}
\begin{tabular}{lccc}
\toprule
指标 & 方法A & 方法B & 本文方法 \\
\midrule
准确率 & 0.85 & 0.89 & \textbf{0.93} \\
召回率 & 0.82 & 0.88 & \textbf{0.91} \\
F1 分数 & 0.83 & 0.88 & \textbf{0.92} \\
\bottomrule
\end{tabular}
\end{table}

% 合并列
\begin{tabular}{lcccc}
\toprule
& \multicolumn{2}{c}{训练集} & \multicolumn{2}{c}{测试集} \\
\cmidrule(lr){2-3} \cmidrule(lr){4-5}
模型 & RMSE & $R^2$ & RMSE & $R^2$ \\
\midrule
线性回归 & 1.23 & 0.85 & 1.45 & 0.82 \\
XGBoost  & 0.87 & 0.94 & 0.92 & 0.91 \\
\bottomrule
\end{tabular}
```

## 图片插入

```latex
% 单图
\begin{figure}[H]
\centering
\includegraphics[width=0.8\textwidth]{figures/chart.png}
\caption{图标题在下方}
\label{fig:chart}
\end{figure}

% 子图
\begin{figure}[H]
\centering
\subcaptionbox{训练集拟合\label{fig:fit_train}}
    {\includegraphics[width=0.48\textwidth]{figures/fit_train.png}}
\subcaptionbox{测试集预测\label{fig:fit_test}}
    {\includegraphics[width=0.48\textwidth]{figures/fit_test.png}}
\caption{模型拟合与预测结果}
\label{fig:fit}
\end{figure}
```

## 交叉引用

```latex
% 引用公式
如公式~\eqref{eq:main} 所示...

% 引用图表
如图~\ref{fig:chart} 所示...
如表~\ref{tab:example} 所示...

% 引用文献
如文献~\cite{ref1} 所述...
```

## 编译与调试

### 编译命令

```bash
# XeLaTeX (推荐，支持中文)
xelatex main.tex
xelatex main.tex  # 两次编译以生成正确的交叉引用

# 带参考文献
xelatex main.tex
bibtex main
xelatex main.tex
xelatex main.tex
```

### 编译工具

```bash
# latexmk 自动编译
latexmk -xelatex main.tex

# 清理辅助文件
latexmk -c
```

### 常见编译错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `! Undefined control sequence` | 命令拼写错误或在环境中不可用 | 检查命令拼写，确认宏包已加载 |
| `! Missing $ inserted` | 在文本模式中使用了数学符号 | 数学符号放入 `$...$` |
| `! Extra alignment tab` | 表格列数与 `&` 数不匹配 | 检查 `\begin{tabular}{...}` 列数 |
| `! File not found` | 图片路径错误 | 使用相对路径，检查扩展名 |
| 中文不显示 | 未用 XeLaTeX 编译 | 使用 `xelatex` 而非 `pdflatex` |

## 禁止事项

- 使用 `pdflatex` 编译中文文档（应使用 `xelatex`）
- 手动加粗表格线（国赛用三线表，不用竖线）
- 图片分辨率过低 (< 150 dpi)
- 公式不编号
- 图表出现在引用之前
- 使用 `\input` 导入中文路径文件（可能编码错误）
