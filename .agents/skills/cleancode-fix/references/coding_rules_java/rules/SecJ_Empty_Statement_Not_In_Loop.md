# SecJ_Empty_Statement_Not_In_Loop

- **规则ID**：130b2d6e-52b2-4aea-8bb1-1ff4c72206f0
- **更新时间**：2025-06-05 04:00:05

---

**【问题级别】**

一般

**【描述】**

不正确的风格

**【正确示例】**

```
public void test01Good() {
    System.out.println("look at the extra semicolon");
}

```
**【错误示例】**

```
public void test01Bad() {
    System.out.println("look at the extra semicolon");
	// the extra semicolon here this is not necessary
    /* POTENTIAL FLAW: 空非循环语句块 */
    ;
}

```
**【修复建议】**
