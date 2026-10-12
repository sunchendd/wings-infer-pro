# SecA_LSW_R_DivideByZero

- **规则ID**：818a935f-9fde-44ed-81d7-b20f5a17f2fe
- **更新时间**：2026-04-07 04:10:01

---

**【问题级别】**

一般

**【描述】**

检查进行算术除法或求模运算时除数为零的场景

**【正确示例】**

```
```
int goodTest() {
    int x = 0;
    if (x>10) {
        x = 1;
    }
    if (x!=0){
        return 1 / x;  //ok    
    }
    return 0;
}


```

```
**【错误示例】**

```
```
int badcase1() {
    int x = 0;
    if (x>10) {
        x = 1;
    }
    return 1 / x;  //err
}
```

```
**【修复建议】**

通过校验变量，让变量被除时，不可能为0。
