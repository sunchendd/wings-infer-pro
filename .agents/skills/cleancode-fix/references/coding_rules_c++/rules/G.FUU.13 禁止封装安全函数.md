# G.FUU.13 禁止封装安全函数

- **规则ID**：de2c7dfe-c19d-4aef-9b20-da1cb592132d
- **更新时间**：2025-03-25 19:24:07

---

**【问题级别】**

一般

**【描述】**

华为安全函数是C11标准的相关标准接口一个实现，在开发时充分考虑了规范要求，安全性，运行效率，可移植性等方面。保留所有安全检查和返回值信息的封装，不必要的增加了函数调用开销；对入参检查及返回值进行修改的封装，丢失了安全函数的部分安全特性。因此安全函数不允许进行封装。



以函数封装的形式重新封装安全函数或不安全函数时，忽略安全函数的destMax参数，或用count参数直接代替destMax参数，具有额外的安全风险。

**【正确示例】**

```
使用华为安全函数
void test_good_case(void *dest, size_t destmax, const void *src, size_t count) 
{
  ...
  errno_t ret = memcpy_s(dest, destmax, src, count);
  ... // 校验ret，确保安全函数执行成功
}

```
**【错误示例】**

```
错误示例1：使用类似不安全函数的接口封装安全函数，destMax与count参数使用相同参数

void *XXX_memcpy(void *dest, const void *src, size_t count)
{
    ...
    memcpy_s(dest,  count,  src, count);
    ...
}
错误示例2：使用函数简单封装安全函数，封装函数的接口入参类型与安全函数入参相同，但封装函数内调用安全函数时destMax与count参数使用相同参数。

errno_t XXX_memcpy_s(void *dest, size_t destMax, const void *src, size_t count)
{
    ...
    memcpy_s(dest,  count,  src, count);
    ...
}
错误示例3：使用类似安全函数的名字的函数，但是参数与安全函数不同

errno_t XXX_memcpy_s(void *dest, const void *src, size_t count)
{
    ...
}
错误示例4：将函数的名字命名为类似安全函数(函数名称内包含安全函数的名字），但实现为危险函数。

errno_t XXX_memcpy_s(void *dest, size_t destmax, const void *src, size_t count)
{
    ...
    memcpy(dest, src, count);
    ...
}
错误示例5：用函数实现自定义不安全函数

errno_t XXX_strncpy(char *dest, size_t destMax, const char *src)
{
    ...
}

```
**【修复建议】**

对安全函数做封装时，正确理解destMax的用法，不要用count替代destMax
