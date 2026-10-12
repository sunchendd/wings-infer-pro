# G.SER.07 防止反序列化被利用来绕过构造方法中的安全操作

- **规则ID**：680bd694-fad9-4230-8146-c5fa5b5d3955
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

致命

**【描述】**

可序列化的类如果在其构造函数中执行 SecurityManager 检查，那么它还需要在其 readObject() 和 readObjectNoData 方法中执行相同的检查。

**【正确示例】**

```
public final class CWE358_J_Rule7_3_Missing_SecurityManager_Check_Serializable_01_Good implements Serializable {
    private static final long serialVersionUID = 9078808681344666097L;

    // Private internal state
    private String town;

    private static final String UNKNOWN = "UNKNOWN";

    public CWE358_J_Rule7_3_Missing_SecurityManager_Check_Serializable_01_Good() {
        // Initialize town to default value
        town = UNKNOWN;
    }

    private void writeObject(ObjectOutputStream out) throws IOException {
        out.writeObject(town);
    }

    private void readObject(ObjectInputStream in) throws Exception {
        in.defaultReadObject();
    }
}

```
**【错误示例】**

```
public final class CWE358_J_Rule7_3_Missing_SecurityManager_Check_Serializable_02_Bad implements Serializable {
    private static final long serialVersionUID = 9078808681344666097L;

    // Private internal state
    private String town;

    private static final String UNKNOWN = "UNKNOWN";

    void performSecurityManagerCheck() throws SecurityException {
        // verify whether current user has rights to access the file
        SecurityManager securityManager = System.getSecurityManager();
    }

    public CWE358_J_Rule7_3_Missing_SecurityManager_Check_Serializable_02_Bad() {
        performSecurityManagerCheck();
        // Initialize town to default value
        town = UNKNOWN;
    }

    /* POTENTIAL FLAW: 1）实现Serializable接口，并且在实现类的构造函数中包含安全检查器 2）基于第一点，工具检测readObject和writeObject方法中是否包含安全检查器，如果没有则报告警。 */
    private void writeObject(ObjectOutputStream out) throws IOException {
        out.writeObject(town);
    }

    /* POTENTIAL FLAW: 1）实现Serializable接口，并且在实现类的构造函数中包含安全检查器 2）基于第一点，工具检测readObject和writeObject方法中是否包含安全检查器，如果没有则报告警。 */
    private void readObject(ObjectInputStream in) throws Exception {
        in.defaultReadObject();
    }
}

```
**【修复建议】**

如果可序列化的类的构造函数中存在 SecurityManager 检查，请确保 readObject() 和 readObjectNoData() 方法中存在相同的 SecurityManager 检查。
