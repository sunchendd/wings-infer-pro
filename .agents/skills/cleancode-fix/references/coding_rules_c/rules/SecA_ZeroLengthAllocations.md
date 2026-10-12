# SecA_ZeroLengthAllocations

- **规则ID**：9ad2b334-d47a-4d88-ab2c-a257970996a0
- **更新时间**：2025-06-05 04:10:01

---

**【问题级别】**

一般

**【描述】**

不能申请0或者负数长度的内存

**【正确示例】**

```


```
**【错误示例】**

```
【Instruction】&nbsp;&nbsp;(1)覆盖函数：malloc、VOS_Malloc、VOS_MemAlloc、new函数
(2)检查申请的内存size大小，如果size一定大于0，则不告警，否则告警。【Example】&nbsp;&nbsp;//good example

void test_good(uint32_t a, uint32_t b)
{
 uint32_t vSize = a; 
 uint32_t hSize = b;
 if (vSize * hSize > 0) {
  uint8_t  *imgBufChn0 = NULL;
  imgBufChn0 = new uint8_t[vSize * hSize];    // ok
 }else {
 }
}



//bad example

void test_bad(uint32_t a, uint32_t b)
{
 uint32_t vSize = a; 
 uint32_t hSize = b;
 if (vSize * hSize > 0) {
 }else {
  uint8_t  *imgBufChn0 = NULL;
  imgBufChn0 = new uint8_t[vSize * hSize];    // error: 此分支 vSize * hSize <= 0
 }
}

```
**【修复建议】**

内存申请长度要在合理范围内
