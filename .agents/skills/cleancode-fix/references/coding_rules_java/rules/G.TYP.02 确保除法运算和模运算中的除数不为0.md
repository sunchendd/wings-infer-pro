# G.TYP.02 确保除法运算和模运算中的除数不为0

- **规则ID**：3ac945d4-c477-4d28-a6d7-7363008f0a5c
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

一般

**【描述】**

如果除法或模运算中的除数为零可能会导致程序终止或拒绝服务（DoS），因此需要在运算前保证除数不为0。



202406新增一个场景：BigDecimal的divide方法调用前先保证除数不为0，该场景目前仅能通过正确示例中的写法消除告警，其他方式误报可申请屏蔽。

**【正确示例】**

```
### 场景1：除数未判断是否为0
- 修复示例1：BigDecimal的devide使用前判断不为0
```java
    public void doSomething(String s) throws Exception {
        BigDecimal bigDecimal = new BigDecimal(s);
        if (bigDecimal.compareTo(BigDecimal.ZERO) != 0) {
            /* GOOD: 除零被除数bigDecimal已经在if中做判断 */
            BigDecimal newBigDecimal = new BigDecimal("100").divide(bigDecimal, MathContext.DECIMAL128);
        }
        ... // 其他逻辑代码
    }
```

- 修复示例2：
```java
private HostAddress getAddr() {
    List<HostAddress> addr = nebulaSessPoolConfig.getGraphAddrArray();
    if (CollectionUtils.isNotEmpty(addr)) { // 校验addr是否为空
        int newPos = (pos.getAndIncrement()) % addr.size();
        return addr.get(newPos);
    }
    ... // 其他逻辑代码
}
```

```
**【错误示例】**

```
##### 场景1：除数未判断是否为0
- 错误示例1：

```java
    public void testcase() {
        long dividendNum = 0;
        int divisorNum1 = 0;
        Integer divisorNum2 = 0;
        /* 不符合: 使用除法运算或模运算没有判断除数大小。 */
        long result1 = dividendNum / divisorNum1;
        /* 不符合: 使用除法运算或模运算没有判断除数大小。 */
        long result2 = dividendNum % divisorNum2;
    }
```
- 错误示例2：

```java
private HostAddress getAddr() {
    List<HostAddress> addr = nebulaSessPoolConfig.getGraphAddrArray();

    // 【不符合】 集合中的元素数量可能为0
    int newPos = (pos.getAndIncrement()) % addr.size();
    return addr.get(newPos);
}
```

```
**【修复建议】**

用作除数的整数，在运算前保证其不为0。
