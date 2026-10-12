# G.OTH.04 禁止在发布版本中输出对象或函数的地址

- **规则ID**：e53adfe4-4aee-4cdc-a589-6d2a30d43fb8
- **更新时间**：2025-03-25 19:23:49

---

**【问题级别】**

一般

**【描述】**

禁止在发布版本中输出对象或函数的地址，如：将变量或函数的地址输出到客户端、日志、串口中。



当攻击者实施高级攻击时，通常需要先获取目标程序中的内存地址（如变量地址、函数地址等），再通过修改指定内存的内容，达到攻击目的。

如果程序中主动输出对象或函数的地址，则为攻击者提供了便利条件，可以根据这些地址以及偏移量计算出其他对象或函数的地址，并实施攻击。

另外，由于内存地址泄露，也会造成地址空间随机化的保护功能失效。



为降低地址泄露造成漏洞的风险，高版本linux内核代码中的printk函数已经将%p格式由打印地址数值修改为打印地址的hash值。

同时也提供了%pK %px等格式，应对特殊场景，因此内核中打印指针的策略可参考业界CVE修改漏洞的方法。

**【正确示例】**

```
如下代码中，删除打印地址的代码。
int Encode(unsigned char *in, size_t inSize, unsigned char *out, size_t maxSize)
{
    ...
    Log("in size=%zu, max size=%zu
", inSize, maxSize);
    ...
}

```
**【错误示例】**

```
如下代码中，使用%p格式将指针指向的地址记录到日志中。
int Encode(unsigned char *in, size_t inSize, unsigned char *out, size_t maxSize)
{
    ...
    Log("in=%p, in size=%zu, out=%p, max size=%zu
", in, inSize, out, maxSize);
    ...
}

```
**【修复建议】**

不要在输出类函数中打印对象或函数的地址。
