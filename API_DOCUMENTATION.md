# 麻将分析 API 文档

## 接口列表

### 1. 健康检查

检查API服务是否正常运行。

**请求**

```http
GET /health
```

**响应**

```json
{
  "status": "ok",
  "message": "Mahjong Analysis API is running"
}
```

**状态码**
- `200 OK`: 服务正常运行

---

### 2. 创建分析任务

创建一个新的麻将游戏分析任务。

**请求**

```http
POST /analysis
Content-Type: application/json
```

**请求体**

```json
{
  "cos_path": "egg/057c3d16-8767-4094-a8f3-1436a1bf7a88/2025-10-24",
  "prompt": "请分析这些麻将游戏截图中的每个玩家的操作",
  "force_reanalyze": false
}
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| cos_path | string | 是 | - | COS存储路径，包含游戏截图PNG文件 |
| prompt | string | 是 | - | 分析提示词，用于指导AI分析方向 |
| force_reanalyze | boolean | 否 | false | 是否强制重新分析已有JSON的图片。如果为true，即使已有JSON文件也会重新分析；如果为false，则跳过已有JSON的图片 |

**功能说明**

1. **智能跳过已分析图片**: 当从COS下载文件时，系统会同时下载PNG和JSON文件。如果某张PNG图片已有对应的JSON分析结果，默认会跳过该图片的分析，直接使用已有结果。

2. **强制重新分析**: 通过设置 `force_reanalyze: true`，可以强制系统重新分析所有图片，即使已存在JSON结果文件。这在以下情况下很有用：
   - 分析模型更新后需要重新生成结果
   - 之前的分析结果有误需要修正
   - 想要使用不同的prompt重新分析

**响应**

```json
{
  "task_id": "85b9949b-f8c4-4855-97fe-8a2bf6e9b644",
  "status": "pending",
  "message": "任务已创建",
  "force_reanalyze": false
}
```

**状态码**
- `201 Created`: 任务创建成功
- `400 Bad Request`: 请求参数错误
- `500 Internal Server Error`: 服务器内部错误

---

### 3. 查询任务状态

查询指定任务的执行状态和进度。

**请求**

```http
GET /analysis/{task_id}
```

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| task_id | string | 任务ID（UUID格式） |

**响应**

```json
{
  "task_id": "85b9949b-f8c4-4855-97fe-8a2bf6e9b644",
  "cos_path": "egg/057c3d16-8767-4094-a8f3-1436a1bf7a88/2025-10-24",
  "prompt": "请分析这些麻将游戏截图中的每个玩家的操作",
  "force_reanalyze": false,
  "status": "completed",
  "created_at": "2025-10-27T10:00:00.123456",
  "updated_at": "2025-10-27T10:05:00.123456",
  "progress": 100,
  "message": "分析完成",
  "error": null,
  "result_file": "/path/to/cache/85b9949b-f8c4-4855-97fe-8a2bf6e9b644.txt",
  "cache_used": false
}
```

**字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | 任务唯一标识符 |
| cos_path | string | COS存储路径 |
| prompt | string | 分析提示词 |
| force_reanalyze | boolean | 是否强制重新分析 |
| status | string | 任务状态（见下表） |
| created_at | string | 任务创建时间（ISO 8601格式） |
| updated_at | string | 任务最后更新时间 |
| progress | integer | 任务进度（0-100） |
| message | string | 当前状态描述信息 |
| error | string/null | 错误信息（失败时） |
| result_file | string/null | 结果文件路径（完成时） |
| cache_used | boolean | 是否使用了本地缓存 |

**任务状态**

| 状态 | 说明 |
|------|------|
| pending | 等待执行 |
| downloading | 正在下载PNG和JSON文件 |
| analyzing | 正在分析图片（会自动跳过已有JSON的图片） |
| merging | 正在合并分析结果 |
| completed | 任务完成 |
| failed | 任务失败 |

**状态码**
- `200 OK`: 查询成功
- `404 Not Found`: 任务不存在
- `500 Internal Server Error`: 服务器内部错误

---

### 4. 获取任务结果

获取任务的最终分析结果（JSON格式，包含完整的txt文件内容）。新增字段 `analysis_data` 会携带与结果文件相同的完整文本内容，便于前端独立读取。

**请求**

```http
GET /analysis/{task_id}/result
```

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| task_id | string | 任务ID（UUID格式） |

**响应**

```json
{
  "task_id": "85b9949b-f8c4-4855-97fe-8a2bf6e9b644",
  "status": "completed",
  "result_file": "/path/to/cache/85b9949b-f8c4-4855-97fe-8a2bf6e9b644.txt",
  "content": "# 麻将游戏分析报告\n\n## 整体概况\n...",
  "analysis_data": "# 麻将游戏分析报告\n\n## 整体概况\n...",
  "size": 12345,
  "created_at": "2025-10-27T10:00:00.123456",
  "updated_at": "2025-10-27T10:05:00.123456"
}
```

**字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | 任务唯一标识符 |
| status | string | 任务状态 |
| result_file | string | 结果文件的完整路径 |
| content | string | 分析结果的完整文本内容 |
| analysis_data | string | 与结果文件一致的完整文本内容（为前端提供的独立字段） |
| size | integer | 文件大小（字节） |
| created_at | string | 任务创建时间 |
| updated_at | string | 任务更新时间 |

**状态码**
- `200 OK`: 获取成功
- `400 Bad Request`: 任务尚未完成
- `404 Not Found`: 任务不存在或结果文件不存在
- `500 Internal Server Error`: 服务器内部错误

---

### 5. 列出所有任务

获取所有任务的列表，支持过滤和分页。

**请求**

```http
GET /tasks?status={status}&limit={limit}
```

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 否 | 过滤任务状态（pending/downloading/analyzing/merging/completed/failed） |
| limit | integer | 否 | 限制返回数量 |

**响应**

```json
{
  "tasks": [
    {
      "task_id": "85b9949b-f8c4-4855-97fe-8a2bf6e9b644",
      "cos_path": "egg/057c3d16-8767-4094-a8f3-1436a1bf7a88/2025-10-24",
      "prompt": "请分析这些麻将游戏截图",
      "force_reanalyze": false,
      "status": "completed",
      "created_at": "2025-10-27T10:00:00.123456",
      "updated_at": "2025-10-27T10:05:00.123456",
      "progress": 100,
      "message": "分析完成",
      "error": null,
      "result_file": "/path/to/result.txt",
      "cache_used": false
    }
  ],
  "total": 1
}
```

**状态码**
- `200 OK`: 查询成功
- `400 Bad Request`: 参数错误（如无效的status值）
- `500 Internal Server Error`: 服务器内部错误

---

### 6. 列出COS目录内容

列出COS存储指定路径下的文件和文件夹。

**请求**

```http
GET /cos/list?path={cos_path}
```

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string | 否 | COS路径，默认为根路径 |

**响应**

```json
{
  "path": "egg/057c3d16-8767-4094-a8f3-1436a1bf7a88/2025-10-24",
  "files": [
    {
      "name": "screenshot1.png",
      "key": "egg/057c3d16-8767-4094-a8f3-1436a1bf7a88/2025-10-24/screenshot1.png",
      "size": 245678,
      "size_human": "240.0KB",
      "last_modified": "2025-10-24T15:30:00",
      "type": "file"
    }
  ],
  "directories": [
    {
      "name": "subdir",
      "key": "egg/057c3d16-8767-4094-a8f3-1436a1bf7a88/2025-10-24/subdir/",
      "type": "directory"
    }
  ],
  "total_files": 10,
  "total_directories": 2
}
```

**状态码**
- `200 OK`: 查询成功
- `500 Internal Server Error`: 服务器内部错误

---
