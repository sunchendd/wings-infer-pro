# G.INC.07-CPP 按照合理的顺序包含头文件

- **规则ID**：9480fc84-f856-43ba-8275-f81835576a91
- **更新时间**：2025-03-25 19:22:53

---

**【问题级别】**

一般

**【描述】**

使用一致的头文件包含顺序可提升可读性, 避免隐藏依赖，建议按照稳定度排序：cpp对应的头文件, C/C++标准库, 系统库的.h, 其他库的.h, 本项目内其他的.h。

**【正确示例】**

```
#include "Foo/Foo.h"

#include <cstdlib>
#include <string>

#include <linux/list.h>
#include <linux/time.h>

#include "platform/Base.h"
#include "platform/Framework.h"

#include "project/public/Log.h"

```
**【错误示例】**

```


```
**【修复建议】**

调整头文件包含顺序
