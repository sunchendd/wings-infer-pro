# G.CTF.03 如果要通过 if 条件表达式来判断是否panic，请优先使用断言-试行

- **规则ID**：48a5bc4f-916a-4d75-997e-05dadeed7489
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

一般

**【描述】**

如果要通过 if 条件表达式来判断是否panic，请优先使用断言

**【正确示例】**

```
let sad_people: Vec<&str> = vec![];
assert!(sad_people.is_empty(), "there are sad people: {:?}", sad_people);

```
**【错误示例】**

```
let sad_people: Vec<&str> = vec![];
if !sad_people.is_empty() {
    panic!("there are sad people: {:?}", sad_people);
}

```
**【修复建议】**

如果要通过 if 条件表达式来判断是否panic，请优先使用断言
