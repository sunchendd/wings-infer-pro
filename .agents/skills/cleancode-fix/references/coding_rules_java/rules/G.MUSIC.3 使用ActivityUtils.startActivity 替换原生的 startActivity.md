# G.MUSIC.3 使用ActivityUtils.startActivity 替换原生的 startActivity

- **规则ID**：3231bc10-7b54-4aa2-95af-ef75102ba4ba
- **更新时间**：2025-06-05 04:00:06

---

**【问题级别】**

一般

**【描述】**

使用ActivityUtils.startActivity 替换原生的 startActivity

**【正确示例】**

```
public void startActivity(Intent intent){
        //可能因为权限不足、目标intent不存在等异常导致应用崩溃
        activity.startActivity(intent);
    }

```
**【错误示例】**

```
public void startActivity(Intent intent) {
        //ActivityUtils有保护不会崩溃，根据返回值做下一步处理
        boolean successJump = ActivityUtils.startActivity(intent);
        if (!successJump) {
             //do something
        }
    }

```
**【修复建议】**

使用ActivityUtils
