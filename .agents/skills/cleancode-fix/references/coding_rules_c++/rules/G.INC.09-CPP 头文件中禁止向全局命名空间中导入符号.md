# G.INC.09-CPP 头文件中禁止向全局命名空间中导入符号

- **规则ID**：bbe5c121-eb92-4075-b637-e282ae723fa2
- **更新时间**：2025-03-25 19:22:54

---

**【问题级别】**

严重

**【描述】**

禁止在头文件中的全局命名空间中使用using-directive导入命名空间、使用using-declaration导入单个符号。但是可以在模块自定义命名空间中以及类、函数等局部作用域中使用它们。





**【正确示例】**

```
// Foo.h
namespace Foo {
using mylib::string;               // 符合：可以在模块自定义命名空间中导入符号

void Foo()
{
    using namespace mylib;         // 符合：在函数作用域内使用using-directive
    ...
}
}

```
**【错误示例】**

```
// Foo.h
#include <mylib/string>
using namespace mylib;             // 不符合：禁止向全局命名空间导入
using mylib::string;               // 不符合：禁止向全局命名空间导入符号

```
**【修复建议】**

在模板自定义命名空间导入符号
