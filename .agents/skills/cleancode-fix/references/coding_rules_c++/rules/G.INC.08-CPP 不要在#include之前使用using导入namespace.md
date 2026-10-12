# G.INC.08-CPP 不要在#include之前使用using导入namespace

- **规则ID**：e44ac1d0-497f-437a-88a6-308a56cb8684
- **更新时间**：2025-03-25 19:22:54

---

**【问题级别】**

严重

**【描述】**

使用using导入命名空间会影响后续代码，易造成符号冲突，所以不要在头文件以及源文件中的#include之前使用using导入命名空间。





**【正确示例】**

```


```
**【错误示例】**

```
// test.cpp
#include "A.h"
using namespace A;           // 在C.h中的#include "B.h"之前导入了A
#include "C.h"

int main()
{
    C::Foo();                // 引发歧义：C.h中的Foo函数调用的是A::Fun还是B::Fun
    return 0；
}

```
**【修复建议】**

将对头文件的包含放到前面
