# 安全TOP问题-指针先使用后判空

- **规则ID**：731b9b7e-a4bf-4767-9daf-e9d229d19630
- **更新时间**：2025-03-25 19:24:02

---

**【问题级别】**

一般

**【描述】**

在解引用指针之后又对其进行null判空

**【正确示例】**

```
void GoodTest01(const char *str)
{
    int *lc = HelpTestBad9();
    if (lc == NULL) {
        return;
    }
    // deref_ptr
    printf("The integer num is %d", *lc);  // ok
}

```
**【错误示例】**

```
void TestBad1(struct Student *stu)
{
    struct FamilyInfo *family = stu->family;
    // deref_ptr: Directly dereferencing pointer "family"
    char *addr = family->addr;
    // POTENTIAL FLAW: check_after_deref
    if (family) {
        return;
    }
}

/*
 * @scene 函数返回的指针变量，直接解引用后再判空
 */
int *ExternalFunc();
void TestBad2()
{
    int *lc = ExternalFunc();
    // deref_ptr: Directly dereferencing pointer "lc"
    printf("The integer num is %d", *lc);
    // POTENTIAL FLAW: check_after_deref
    if (lc == NULL) {
        return;
    }
}

```
**【修复建议】**

1.判空操作应该在解引用之前

2.冗余判空可以删除
