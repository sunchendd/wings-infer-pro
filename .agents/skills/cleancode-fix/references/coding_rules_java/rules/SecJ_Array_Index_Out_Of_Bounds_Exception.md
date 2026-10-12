# SecJ_Array_Index_Out_Of_Bounds_Exception

- **规则ID**：575884cb-4812-4493-aae8-ca9227fcb9e4
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

一般

**【描述】**

获取的外部Intent列表或数组数据引用前，校验长度合法性，最好能够增加try-catch异常捕获块。如果未对长度做合法性校验就直接引用，可能导致数组越界异常。

**【正确示例】**

```
```java

public void right() {

Bundle data = new Bundle();

// 【GOOD】获取的外部Intent列表或数组数据，增加ArrayIndexOutOfBoundsException|IndexOutOfBoundsException|Exception的异常保护

try {

ArrayList<String> types = data.getStringArrayList("");

} catch (ArrayIndexOutOfBoundsException e) {

}

}

```

```
**【错误示例】**

```
```java

public void wrong() {

Bundle data = new Bundle();

// 【不符合】获取的外部Intent列表或数组数据，未对长度做合法性校验就直接引用，可能导致数组越界异常。

ArrayList<String> types = data.getStringArrayList("");

}

```

```
**【修复建议】**

获取的外部Intent列表或数组数据引用前，校验长度合法性，最好能够增加try-catch异常捕获块，增加ArrayIndexOutOfBoundsException|IndexOutOfBoundsException|Exception的异常保护。
