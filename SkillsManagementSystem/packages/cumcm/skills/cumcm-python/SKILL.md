---
name: cumcm-python
description: CUMCM Python 数据科学与编程技能。涵盖：数据读取与清洗、缺失值/异常值处理、标准化、统计分析、可视化、模型实现、结果输出。使用 NumPy、Pandas、Matplotlib、SciPy、scikit-learn、statsmodels、networkx、pulp、xgboost、lightgbm。触发：用户提到"代码""编程""Python""数据分析""画图""求解"等。
---

# CUMCM Python 数据科学与编程

## 核心原则

代码必须：**可复现、模块化、直接可用**。每个脚本独立可运行，结果自动保存。

## 项目结构模板

每次比赛开始，自动创建：

```
project/
├── data/           # 原始数据 + 清洗后数据
├── scripts/        # 所有 .py 脚本
│   ├── 1_data_preprocess.py
│   ├── 2_explore_analysis.py
│   ├── 3_model_<name>.py
│   └── 4_visualize.py
├── models/         # 模型保存 (pickle/joblib)
├── figures/        # 图表 (300 dpi PNG + PDF)
├── tables/         # 结果表格 (Excel/CSV)
├── paper/          # 论文相关
├── results/        # 最终结果汇总
└── requirements.txt
```

## 标准代码模板

### 1. 数据读取

```python
import pandas as pd
import numpy as np

# CSV (UTF-8)
df = pd.read_csv("data/raw.csv", encoding="utf-8")

# CSV (GBK, 国赛常见)
df = pd.read_csv("data/raw.csv", encoding="gbk")

# Excel (第一个 sheet)
df = pd.read_excel("data/raw.xlsx", sheet_name=0)

# Excel (指定 sheet 名)
df = pd.read_excel("data/raw.xlsx", sheet_name="Sheet1")

# 多 sheet 读取
sheets = pd.read_excel("data/raw.xlsx", sheet_name=None)
for name, sheet in sheets.items():
    print(f"Sheet: {name}, Shape: {sheet.shape}")
```

### 2. 数据清洗

```python
# 缺失值检查
missing = df.isnull().sum()
missing_pct = df.isnull().sum() / len(df) * 100
print(pd.DataFrame({"缺失数": missing, "缺失率(%)": missing_pct}))

# 缺失值处理
df_filled = df.fillna(df.mean())           # 均值填充
df_filled = df.fillna(df.median())          # 中位数填充
df_filled = df.fillna(method="ffill")       # 前向填充 (时间序列)
df_filled = df.interpolate(method="linear") # 线性插值
df_dropped = df.dropna()                    # 删除含缺失行
df_dropped_col = df.dropna(axis=1)          # 删除含缺失列

# 异常值检测 (3σ 原则)
for col in df.select_dtypes(include=[np.number]).columns:
    mean, std = df[col].mean(), df[col].std()
    outliers = df[(df[col] < mean - 3*std) | (df[col] > mean + 3*std)]
    if len(outliers) > 0:
        print(f"{col}: {len(outliers)} 个异常值")

# IQR 异常值检测
Q1 = df[col].quantile(0.25)
Q3 = df[col].quantile(0.75)
IQR = Q3 - Q1
lower, upper = Q1 - 1.5*IQR, Q3 + 1.5*IQR
outliers = df[(df[col] < lower) | (df[col] > upper)]

# 重复值
df = df.drop_duplicates()
```

### 3. 数据标准化

```python
from sklearn.preprocessing import StandardScaler, MinMaxScaler

# Z-score 标准化 (PCA/聚类前)
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Min-Max 归一化 [0,1] (神经网络前)
scaler = MinMaxScaler()
X_norm = scaler.fit_transform(X)

# 手动归一化
X_norm = (X - X.min()) / (X.max() - X.min())
```

### 4. 描述性统计

```python
desc = df.describe()
desc.to_excel("tables/descriptive_stats.xlsx")

# 相关性分析
corr_matrix = df.corr()
corr_matrix.to_excel("tables/correlation.xlsx")
```

### 5. 可视化 (国赛风格)

```python
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["SimHei"]  # 中文显示
matplotlib.rcParams["axes.unicode_minus"] = False    # 负号显示

# 全局设置
plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "font.size": 11,
})

def save_fig(fig, name):
    """保存图表到 figures/ 目录"""
    fig.savefig(f"figures/{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(f"figures/{name}.pdf", bbox_inches="tight")
    plt.close(fig)

# 折线图
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(x, y, "o-", color="#2E75B6", linewidth=1.5, markersize=4, label="标签")
ax.set_xlabel("X轴标签")
ax.set_ylabel("Y轴标签")
ax.set_title("图表标题")
ax.legend()
ax.grid(True, alpha=0.3)
save_fig(fig, "line_chart")

# 柱状图
fig, ax = plt.subplots(figsize=(8, 5))
colors = ["#2E75B6", "#E74C3C", "#27AE60", "#F39C12"]
ax.bar(labels, values, color=colors[:len(labels)], edgecolor="white", linewidth=0.5)
ax.set_ylabel("值")
ax.set_title("柱状图")
save_fig(fig, "bar_chart")

# 热力图 (相关性)
fig, ax = plt.subplots(figsize=(10, 8))
im = ax.imshow(corr_matrix, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
plt.colorbar(im, ax=ax)
ax.set_xticks(range(len(corr_matrix.columns)))
ax.set_xticklabels(corr_matrix.columns, rotation=45, ha="right")
ax.set_yticks(range(len(corr_matrix.columns)))
ax.set_yticklabels(corr_matrix.columns)
save_fig(fig, "heatmap")

# 散点图
fig, ax = plt.subplots(figsize=(8, 5))
scatter = ax.scatter(x, y, c=color_var, cmap="viridis", s=30, alpha=0.7)
plt.colorbar(scatter, ax=ax)
ax.set_xlabel("X轴")
ax.set_ylabel("Y轴")
save_fig(fig, "scatter")

# 双Y轴
fig, ax1 = plt.subplots(figsize=(8, 5))
ax2 = ax1.twinx()
ax1.plot(x, y1, "o-", color="#2E75B6", label="Y1")
ax2.plot(x, y2, "s--", color="#E74C3C", label="Y2")
ax1.set_xlabel("X")
ax1.set_ylabel("Y1", color="#2E75B6")
ax2.set_ylabel("Y2", color="#E74C3C")
save_fig(fig, "dual_axis")

# 多子图
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
axes = axes.flatten()
for i, (ax, col) in enumerate(zip(axes, df.columns[:4])):
    ax.plot(df.index, df[col], linewidth=1)
    ax.set_title(col)
    ax.grid(True, alpha=0.3)
plt.tight_layout()
save_fig(fig, "multi_subplot")
```

## 各模型标准实现

### 灰色预测 GM(1,1)

```python
def gm11(x0, predict_n=1):
    """
    GM(1,1) 灰色预测
    x0: 原始序列 (list/array)
    predict_n: 预测步数
    returns: (拟合值, 预测值, 后验差比值C, 小误差概率P)
    """
    import numpy as np
    x0 = np.array(x0, dtype=float)
    n = len(x0)
    # 1-AGO
    x1 = np.cumsum(x0)
    # 紧邻均值生成
    z1 = 0.5 * (x1[1:] + x1[:-1])
    B = np.column_stack([-z1, np.ones(n-1)])
    Y = x0[1:]
    # 最小二乘
    u = np.linalg.inv(B.T @ B) @ B.T @ Y
    a, b = u[0], u[1]
    # 时间响应函数
    def predict(k):
        return (x0[0] - b/a) * np.exp(-a*k) + b/a
    # 拟合值
    x1_hat = np.array([predict(k) for k in range(n + predict_n)])
    x0_hat = np.diff(x1_hat, prepend=0)
    # 精度检验
    e = x0 - x0_hat[:n]
    C = np.std(e) / np.std(x0)  # 后验差比值
    small_err = np.sum(np.abs(e - np.mean(e)) < 0.6745*np.std(x0)) / n
    return x0_hat[:n], x0_hat[n:], C, small_err
```

### TOPSIS (熵权法赋权)

```python
def entropy_topsis(X):
    """
    熵权法 + TOPSIS 综合评价
    X: ndarray (n_samples, n_criteria)
    returns: (scores, ranks, weights)
    """
    import numpy as np
    # 正向化 (假设已全部转为极大型)
    # 标准化
    X_norm = X / np.sqrt((X**2).sum(axis=0))
    # 熵权法
    p = X_norm / X_norm.sum(axis=0)
    p = np.where(p == 0, 1e-10, p)
    e = -np.sum(p * np.log(p), axis=0) / np.log(len(X))
    w = (1 - e) / (1 - e).sum()
    # TOPSIS
    X_weighted = X_norm * w
    ideal_best = np.max(X_weighted, axis=0)
    ideal_worst = np.min(X_weighted, axis=0)
    d_best = np.sqrt(((X_weighted - ideal_best)**2).sum(axis=1))
    d_worst = np.sqrt(((X_weighted - ideal_worst)**2).sum(axis=1))
    scores = d_worst / (d_best + d_worst)
    ranks = np.argsort(-scores) + 1
    return scores, ranks, w
```

### PCA 降维

```python
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

def pca_analysis(X, n_components=None):
    """PCA 分析，返回降维结果、解释方差、载荷矩阵"""
    X_scaled = StandardScaler().fit_transform(X)
    if n_components is None:
        pca = PCA().fit(X_scaled)
    else:
        pca = PCA(n_components=n_components).fit(X_scaled)
    # 累积解释方差
    cumsum_var = np.cumsum(pca.explained_variance_ratio_)
    # 载荷矩阵
    loadings = pca.components_.T * np.sqrt(pca.explained_variance_)
    return pca.transform(X_scaled), cumsum_var, loadings, pca
```

### K-Means 聚类 (含最优 K 选择)

```python
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

def find_best_k(X, k_range=range(2, 10)):
    """使用轮廓系数和肘部法则选最优 K"""
    scores = []
    inertias = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X)
        inertias.append(km.inertia_)
        scores.append(silhouette_score(X, labels))
    best_k = k_range[np.argmax(scores)]
    return best_k, scores, inertias
```

### XGBoost 回归

```python
import xgboost as xgb
from sklearn.model_selection import train_test_split, GridSearchCV

def xgb_regression(X, y, param_grid=None):
    """XGBoost 回归 + 超参数搜索 + 特征重要性"""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42)
    if param_grid is None:
        param_grid = {
            "n_estimators": [100, 200],
            "max_depth": [3, 5, 7],
            "learning_rate": [0.01, 0.1],
        }
    model = GridSearchCV(
        xgb.XGBRegressor(objective="reg:squarederror", random_state=42),
        param_grid, cv=5, scoring="neg_mean_squared_error", n_jobs=-1)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    importance = model.best_estimator_.feature_importances_
    return model, y_test, y_pred, importance
```

## 结果输出规范

```python
# 表格输出
result_df.to_excel("tables/result.xlsx", index=False)
result_df.to_csv("tables/result.csv", index=False, encoding="utf-8-sig")

# 模型保存
import joblib
joblib.dump(model, "models/model.pkl")

# 参数日志
import json
params = {"model": "XGBoost", "R2": 0.95, "RMSE": 1.23}
with open("results/params.json", "w", encoding="utf-8") as f:
    json.dump(params, f, ensure_ascii=False, indent=2)

# 随机种子 (可复现)
import random
random.seed(42)
np.random.seed(42)
```

## 禁止事项

- 不设置随机种子
- 不保存中间结果
- 不检查数据类型 (object 列混入数值计算)
- `SettingWithCopyWarning` 不处理
- 图表不标单位
- 在循环中反复读取大文件
