# G.INC.04-CPP 头文件必须采取保护措施，防止重复包含

- **规则ID**：cc4d0da3-0db2-4d35-a1a0-3433bcca91e8
- **更新时间**：2025-03-25 19:22:51

---

**【问题级别】**

严重

**【描述】**

可以使用#define宏和#pragma once两种方式防止头文件重复包含，项目组可自行决策选择使用一种方式，鼓励使用方式统一。对于#pragma once，使用时注意其适用条件。



鉴于#pragma once有一定的适用条件，本条款推荐优先使用保护宏的方式。



方式一：使用保护宏



定义包含保护符时，应该遵守如下规则：

1）保护符使用唯一名字；

2）不要在受保护部分的前后放置代码或注释，文件头注释除外。

**【正确示例】**

```
#ifndef VOS_INCLUDE_TIMER_TIMER_H
#define VOS_INCLUDE_TIMER_TIMER_H
...
#endif
#ifndef TIMER_H
#define TIMER_H
...
#endif

```
**【错误示例】**

```


```
**【修复建议】**

添加#define保护头文件
