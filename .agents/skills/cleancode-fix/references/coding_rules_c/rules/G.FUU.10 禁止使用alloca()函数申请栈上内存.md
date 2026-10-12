# G.FUU.10 禁止使用alloca()函数申请栈上内存

- **规则ID**：0ae062cb-804a-4fe3-99e0-191f540b5122
- **更新时间**：2026-04-07 04:10:04

---

**【问题级别】**

一般

**【描述】**

POSIX和C99均未定义alloca()的行为，在有些平台下不支持该函数，使用alloca会降低程序的兼容性和可移植性，该函数在栈帧里申请内存，申请的大小很可能超过栈的边界，影响后续的代码执行。



请使用malloc从堆中动态分配内存。

**【正确示例】**

```
// 使用malloc()函数
char *newPtr = (char *)malloc(NEW_SIZE);
if (newPtr == NULL) {
  ... // 错误处理
}
errno_t ret = memcpy_s(newPtr, NEW_SIZE, oldPtr, oldSize);
... // 校验ret，确保安全函数执行成功
... // 返回前，释放oldPtr

```
**【错误示例】**

```
POSIX和C99均未定义alloca()的行为，在有些平台下不支持该函数，使用alloca会降低程序的兼容性和可移植性，该函数在栈帧里申请内存，申请的大小很可能超过栈的边界，影响后续的代码执行。

请使用malloc从堆中动态分配内存。

```
**【修复建议】**

禁止调用realloc和alloca函数
