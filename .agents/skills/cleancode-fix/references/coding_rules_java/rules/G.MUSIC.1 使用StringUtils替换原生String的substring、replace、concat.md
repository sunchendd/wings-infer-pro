# G.MUSIC.1 使用StringUtils替换原生String的substring、replace、concat

- **规则ID**：5513bae3-254d-40ab-b853-69534ee62bf8
- **更新时间**：2025-06-05 04:00:06

---

**【问题级别】**

一般

**【描述】**

使用StringUtils替换原生String的substring、replace、concat

**【正确示例】**

```
public String getSafeUid(int index) {
        String originUid = mUser.getUid();
        //可能存在越界风险
        return originUid.substring(index);
    }

```
**【错误示例】**

```
public String getSafeUid(int index) {
        String originUid = mUser.getUid();
        //有保护不会崩溃，越界返回空
        return StringUtils.substring(originUid, index);
    }

```
**【修复建议】**

使用StringUtils
