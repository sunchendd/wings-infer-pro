# G.INC.10-CPP 不要在头文件中使用匿名namespace或static定义非外部可见符号

- **规则ID**：fa9c2d72-bfb8-40e4-9ef3-ff4bf58b85a0
- **更新时间**：2025-03-25 19:22:55

---

**【问题级别】**

严重

**【描述】**

匿名namespace内定义的内容仅对当前编译单元可见（符号不具有外部链接属性）。头文件中使用匿名namespace，实际效果等同于为包含了此头文件的源文件定义了一组私有成员，而头文件一般用于定义模块间的公共接口，因此这种用法容易引起混淆，不建议使用。



static修饰的全局作用域的变量或函数也有类似的作用，同样不建议在头文件中使用。

**【正确示例】**

```
##### 场景1：在头文件中使用匿名namespace定义非外部可见符号
- 修复示例：
```cpp
// Counter.h

// 符合：没有使用匿名namespace
...

// Counter.cpp
namespace { // 符合：如果是非外部可见符号，可在cpp文件中使用匿名namespace封装或者使用static修饰
int g_counter = 0;
void DoCount() { g_counter++; }
}
```
##### 场景2：在头文件中使用static定义非外部可见符号
- 修复示例：

```cpp
// Counter.h

// 符合：没有使用static
...

// Counter.cpp
static int g_num = 0;       // 符合：如果是非外部可见符号，可在cpp文件中使用匿名namespace封装或者使用static修饰
static inline void Add()    // 符合：如果是非外部可见符号，可在cpp文件中使用匿名namespace封装或者使用static修饰
{
    g_num++;
}
```

```
**【错误示例】**

```
// Counter.h
namespace {
int g_counter = 0;

void DoCount() { g_counter++; }
}
// Connect1.cpp
#include "Counter.h"

void OnConnect1() { DoCount(); }
// Connect2.cpp
#include "Counter.h"

void OnConnect2() { DoCount(); }

```
**【修复建议】**

仔细审视代码逻辑，确定是否需要修改
