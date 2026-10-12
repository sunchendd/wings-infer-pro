# SecJ_String_Split_Bound_Check

- **规则ID**：7c9222b7-0e2e-4b06-8667-df1871a3135b
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

对使用String.split得到的结果数组访问时，需要对索引值进行合法性检查，避免数组越界异常：java.lang.IndexOutOfBoundsException

**【正确示例】**

```
```java

public void test01Good(int index) {

String source = "<br/>";

String[] infos = source.split("<br/>");

// 【GOOD】使用前对数组下标进行检查

if (index >= 0 && index < infos.length) {

String poiName = infos[index];

}

}

```

```
**【错误示例】**

```
```java

public void test01Bad(int index) {

String source = "<br/>";

String[] infos = source.split("<br/>");

/* 【不符合】在使用String.split得到的结果数组前，未对数组进行长度检查，取字段的时候可能发生越界而导致 Crash。 */

String poiName = infos[index];

}

```

```
**【修复建议】**

对使用String.split得到的结果数组访问时，需要对索引值进行合法性检查
