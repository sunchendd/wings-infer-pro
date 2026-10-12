# G.PRE.07 宏的名称不应与关键字相同

- **规则ID**：f0354336-38cd-4b83-8781-01b262ae2916
- **更新时间**：2026-04-07 04:10:02

---

**【问题级别】**

严重

**【描述】**

宏的名称与关键字（例如int、long、if、while等）相同会导致代码可读性差，也会导致程序未定义行为。

**【正确示例】**

```
##### 场景1：宏名和int重名
- 修复示例：

```c
#define DevId OTHER_TYPE // 符合：不要和关键字相同
#include <stdlib.h>
```
##### 场景2：宏名和while重名
- 修复示例：

```c
#define Traverse(x) for (; (x);) // 符合：不要和关键字相同
```
##### 场景3：宏名和const重名
- 修复示例：

```c
#define OTHER_DEFINE    // 符合：不要和关键字相同

int main()
{
    const int i = 0;
    i++;                // 编译报错

    return 0;
}
```


```
**【错误示例】**

```
##### 场景1：宏名和int重名
- 错误示例：

```c
// 不符合：改变了int的行为，导致后面包含标准头文件时，程序出现未定义的行为
#define int OTHER_TYPE
#include <stdlib.h>
```
##### 场景2：宏名和while重名
- 错误示例：

```c
#define while(x) for (; (x);) // 不符合：重定义关键字
```
##### 场景3：宏名和const重名
- 错误示例：

```c
#define const           // 不符合：重定义关键字

int main()
{
    const int i = 0;    // 期望是定义常量，但实际是变量
    i++;                // 这里编译不报错

    return 0;
}
```


```
**【修复建议】**

修改宏名，不要和关键字相同，如：



```c

break：用于跳出循环或switch语句。

else：用于定义if语句中的否定分支。

case：用于定义switch语句中的分支。

enum：用于定义枚举类型。

char：用于声明字符类型。

extern：用于声明外部变量或函数。

const：用于声明常量。

float：用于声明单精度浮点数类型。

continue：用于跳过当前循环的剩余部分。

for：用于定义for循环。

default：用于定义switch语句中的默认分支。

goto：用于无条件跳转到指定的标签。

do：用于定义do-while循环。

if：用于定义条件语句。

double：用于声明双精度浮点数类型。

inline：用于声明内联函数。

int：用于声明整数类型。

long：用于声明长整数类型。

register：用于声明寄存器变量。

return：用于从函数中返回值。

short：用于声明短整数类型。

signed：用于声明有符号类型。

sizeof：用于获取变量或类型的大小。

static：用于声明静态变量或函数。

struct：用于定义结构体类型。

switch：用于定义多分支选择语句。

typedef：用于定义类型别名。

union：用于定义联合类型。

unsigned：用于声明无符号类型。

void：用于声明无类型。

volatile：用于声明易变变量。

...

```
