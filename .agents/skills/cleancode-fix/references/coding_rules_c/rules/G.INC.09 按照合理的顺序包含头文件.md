# G.INC.09 按照合理的顺序包含头文件

- **规则ID**：74ee9513-30c9-4723-a533-80b4004df905
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

一般

**【描述】**

头文件包含顺序不合理可能会导致编译错误或者程序运行时出现未定义的行为。因此，在编写代码时，应该按照合理的顺序包含头文件。

**【正确示例】**

```
##### 场景1：头文件包含顺序不合理
- 修复示例：

```c
#include "huawei-include-order-oh.h"    // 符合：源文件对应头文件放最后一个，也可以放第一个

#include <string.h>
#include <stdio.h>

#include "huawei-header-guard.h"        // 符合
```

```
**【错误示例】**

```
##### 场景1：头文件包含顺序不合理
- 错误示例：huawei-include-order-oh.c中包含的头文件的次序如下

```c
#include "huawei-include-order-oh.h"
#include "huawei-header-guard.h"        // 不符合
#include <string.h>
#include <stdio.h>
```

```
**【修复建议】**

1. 建议按稳定度包含头文件，依次顺序为：

C标准库，操作系统库，平台库，项目公共库，自己其他的依赖。

2. 对于源文件对应的头文件，可以放最后一个，也可以放第一个。放第一个可用于验证自包含。

推荐使用[Huawei CodeCheck插件](https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305?l=zh-cn)的自动修复/一键格式化功能，详细使用说明见。
