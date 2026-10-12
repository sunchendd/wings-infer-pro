# G.EXP.07-CPP 禁止依赖不同编译单元内全局对象的初始化顺序

- **规则ID**：53daa928-9839-4846-b503-11b2dfa2e41a
- **更新时间**：2025-03-25 19:22:29

---

**【问题级别】**

一般

**【描述】**

不同编译单元内全局对象的初始化顺序没有被严格定义，因此编写代码时要避免依赖全局对象的初始化顺序，否则程序可能产生未定义行为。

**【正确示例】**

```
##### 场景1：依赖全局对象初始化顺序
- 修复示例：全局对象定义时初始化确定值，在程序执行前通过初始化函数获取预期值。（本修复方法不唯一）

```cpp
// file1.cpp
#include "Counter.h"

Counter g_next{0}; // 符合

void InitCounter()
{
    g_next.SetCount(g_current.GetCount() + 1);
}

// file2.cpp
#include "Counter.h"

Counter g_current{10};
```

```
**【错误示例】**

```
在file1.cpp中使用 g_current 初始化 g_next，但是 g_current 是在file2.cpp中定义的，可能还没有被初始化。

// file1.cpp
#include "Counter.h"

Counter g_next{g_current.GetCount() + 1};

// file2.cpp
#include "Counter.h"

Counter g_current{10};

```
**【修复建议】**

不要依赖全局对象的初始化顺序
