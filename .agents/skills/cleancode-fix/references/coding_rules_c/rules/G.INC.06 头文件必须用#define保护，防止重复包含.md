# G.INC.06 头文件必须用#define保护，防止重复包含

- **规则ID**：108e9e60-a0ec-4f1d-93ab-284f3e65c6c0
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

严重

**【描述】**

为防止头文件被重复包含，所有头文件都应当使用 #define作为包含保护；不要使用 #pragma once。



定义包含保护符时，应该遵守如下规则：

 - 保护符使用唯一名称；

- 建议考虑项目源代码树顶层以下的文件路径，不要在受保护部分的前后放置代码或者注释，文件头注释除外。

**【正确示例】**

```
##### 场景1：保护符命名时，首尾是下划线(_)
- 修复示例：

```c
#ifndef VOS_INCLUDE_TIME_H      // 符合：保护符命名时，避免首尾是下划线`_`
#define VOS_INCLUDE_TIME_H
...
#endif
```
##### 场景2：使用`#pragma once`
- 修复示例：

```c
#ifndef VOS_INCLUDE_TIME_H  // 符合
#define VOS_INCLUDE_TIME_H
...
#endif
```
##### 场景3：保护符不唯一
- 修复示例：

```c
// vos/path1/time.h
#ifndef VOS_PATH1_TIME_H // 符合：保护符使用唯一名称
#define VOS_PATH1_TIME_H
...
#endif

// vos/path2/time.h
#ifndef VOS_PATH2_TIME_H // 符合：保护符使用唯一名称
#define VOS_PATH2_TIME_H
...
#endif
```
##### 场景4：`#define`和`#ifndef`名称不一样
- 修复示例：

```c
#ifndef VOS_INCLUDE_TIME_H
#define VOS_INCLUDE_TIME_H  // 符合
...
#endif
```


```
**【错误示例】**

```
##### 场景1：保护符命名时，首尾是下划线(_)
- 错误示例：

```c
#ifndef _VOS_INCLUDE_TIME_H_    // 不符合
```
##### 场景2：使用`#pragma once`
- 错误示例：

```c
#pragma once                // 不符合
```
##### 场景3：保护符不唯一
- 错误示例：

```c
// vos/path1/time.h
#ifndef TIME_H
#define TIME_H
...
#endif

// vos/path2/time.h
#ifndef TIME_H // 不符合：命名不唯一
#define TIME_H
...
#endif
```
##### 场景4：`#define`和`#ifndef`名称不一样
- 错误示例：
```c
#ifndef VOS_INCLUDE_TIME_H
#define TIME_H               // 不符合：和前面的`#ifndef`名称不一样
...
#endif
```


```
**【修复建议】**

1. 不要使用`#pragma once`来防止头文件被重复包含，要使用`#define`。

2. 定义包含保护符`#define`时，应该遵守如下规则：

    - 保护符命名时，避免首尾是下划线`_`；

    - 保护符使用唯一名称；

    - 建议考虑项目源代码树顶层以下的文件路径，不要在受保护部分的前后放置代码或者注释，文件头注释除外。
