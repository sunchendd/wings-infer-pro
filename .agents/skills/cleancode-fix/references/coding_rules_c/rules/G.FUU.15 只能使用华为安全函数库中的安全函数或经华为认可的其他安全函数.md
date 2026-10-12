# G.FUU.15 只能使用华为安全函数库中的安全函数或经华为认可的其他安全函数

- **规则ID**：78387619-5e1b-470e-8fda-f8a117496adf
- **更新时间**：2026-04-07 04:10:05

---

**【问题级别】**

一般

**【描述】**

Huawei Secure C库中提供的安全函数符合C11标准中已有的定义，并结合产品诉求，在平台兼容性和执行效率上有其独特优势。使用类似名称创建的函数难以与C11标准中的函数定义相适配，同时也容易与Huawei Secure C的实现产生混淆，造成误用，并引入安全风险。因此不应当实现私有的安全函数。



同时业界有些公司、组织也提供了安全函数库，经过评估，华为认为如下安全函数也是允许使用的：

1、微软的安全增强函数（Windows平台, Security-Enhanced Versions of CRT Functions）;

微软安全函数检测到运行时错误时，默认处理方式是使程序崩溃退出。由于在安全函数中退出了程序，所以检查安全函数返回值的代码变成了无效代码。

如果不希望程序出现此类退出的现象，需要在程序启动时使用_set_invalid_parameter_handler()函数指定自定义的出错处理函数代替默认处理函数，使检查安全函数返回值的做法有效。



void IgnoreHandler(const wchar_t *expression,

                   const wchar_t *function,

                   const wchar_t *file,

                   unsigned int line,

                   uintptr_t pReserved)

{

    ... // 不做退出处理

}



int main(int argc, char *argv[])

{

    _invalid_parameter_handler oldHandler =

        _set_invalid_parameter_handler(IgnoreHandler);

    ...

    char buf[MAX_LEN];

    errno_t ret = strcpy_s(buf, sizeof(buf), argv[1]);

    if (ret != 0) {

        ... // 错误处理

    }

    ...

    return 0;

}

2、UEFI的安全增强函数（BIOS）。

**【正确示例】**

```
使用华为安全函数库中的安全函数
文件名：memcpy_s.c
/*POTENTIAL FLAW:self defined safe func "memcpy_s"*/
void memcpy_s(char *dest,size_t destMax, char *src, size_t count)
{
    ...
}

```
**【错误示例】**

```
在下面的拷贝安全函数实现中，由于不恰当的进行了类型转换，因此缺乏在64位系统上的可移植性，同时，该函数的返回值也不兼容C11标准中的安全拷贝函数memcpy_s。

#define SECUREC_MEM_MAX_LEN (0x7fffffffUL)
void MemcpySafe(void *dest, unsigned int destMax,
                const void *src, unsigned int count)
{
    if (destMax == 0 || destMax > SECUREC_MEM_MAX_LEN ) {
        return;
    }
    if (dest == NULL || src == NULL) {
        return;
    }
    if (count > destMax) {
        return;
    }
    if (dest == src) {
        return;
    }
    if (((uint32_t)dest > (uint32_t)src &&
         (uint32_t)dest < (uint32_t)(void *)((uint8_t *)src + count)) ||
        ((uint32_t)src > (uint32_t)dest &&
         (uint32_t)src < (uint32_t)(void *)((uint8_t *)dest + count))) {
        return;
    }
    memcpy(dest, src, count);
}

```
**【修复建议】**

不要自定义安全函数。
