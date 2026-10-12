# G.FUU.21 禁止使用内存操作类不安全函数

- **规则ID**：42d0640e-eb55-4909-9336-776d1b3b20e6
- **更新时间**：2025-03-25 19:24:14

---

**【问题级别】**

严重

**【描述】**

C语言标准的许多函数，要求程序员提供足够大的数组（内存空间）以容纳函数产生的结果。但是根据历史漏洞分析，程序员在使用一些内存操作类函数时，容易因使用不当而造成缓冲区溢出等安全漏洞。因此本规范中禁止使用内存操作类不安全函数。为避免遗漏对不安全函数的检查，同时禁止封装这些不安全函数。



基于缓冲区溢出漏洞触发的历史情况分析并统计，发现有很大一部分缓冲区溢出漏洞是因为调用了这些内存操作类函数但未考虑目标缓冲区大小而导致的。



以下列出了部分内存操作类不安全函数：



内存拷贝函数：memcpy(), wmemcpy(), memmove(), wmemmove()

内存初始化函数：memset()

字符串拷贝函数：strcpy(), wcscpy(), strncpy(), wcsncpy()

字符串拼接函数：strcat(), wcscat(), strncat(), wcsncat()

字符串格式化输出函数：sprintf(), swprintf(), vsprintf(), vswprintf(), snprintf(), vsnprintf()

字符串格式化输入函数：scanf(), wscanf(), vscanf(), vwscanf(), fscanf(), fwscanf(), vfscanf(), vfwscanf(), sscanf(), swscanf(), vsscanf(), vswscanf()

stdin流输入函数：gets()

请使用对应的安全函数，详细信息请参见附录I 不安全函数及替换的安全函数列表。

**【正确示例】**

```
void riskyFunc_good(char* src)
{
    char dest[16] = {0};
    // 推荐使用安全函数，增加destMax参数，对目的缓冲区做保护
    memcpy_s(dest, sizeof(dest), p, strlen(src));
}

```
**【错误示例】**

```
部分内存操作类不安全函数：
内存拷贝函数：memcpy(), wmemcpy(), memmove(), wmemmove()
内存初始化函数：memset()
字符串拷贝函数：strcpy(), wcscpy(), strncpy(), wcsncpy()
字符串拼接函数：strcat(), wcscat(), strncat(), wcsncat()
字符串格式化输出函数：sprintf(), swprintf(), vsprintf(), vswprintf(), snprintf(), vsnprintf()
字符串格式化输入函数：scanf(), wscanf(), vscanf(), vwscanf(), fscanf(), fwscanf(), vfscanf(), vfwscanf(), sscanf(), swscanf(), vsscanf(), vswscanf()
stdin流输入函数：gets()

```
**【修复建议】**

使用安全函数替代危险函数。
