# G.SAF.UNS.01 禁止将外部数据作为加载动态库的参数

- **规则ID**：a513932e-178f-4415-ba03-968ed9777e49
- **更新时间**：2026-04-07 04:40:01

---

**【问题级别】**

一般

**【描述】**

禁止将从外部获取的数据作为加载动态库的参数，否则可能加载攻击者事先预制的模块。

**【正确示例】**

```
```
extern crate libloading;
use std::ffi::OsStr;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    fn whitelist_verify<P: AsRef<OsStr>>(lib_path: P) -> Result<bool, String> {
        // 检查传入路径是否在白名单内
        // ......
        return Result::Ok(false);
    }

    let name = "nagisa64.dll";
    if whitelist_verify(name).is_ok() {
        return;
    }
    unsafe {
        let lib = libloading::Library::new(name);
        if lib.is_err() {
            println!("can't open {}", name);
        }
    }

}
```

```
**【错误示例】**

```
```
let mut f = std::fs::File::open("tests/nagisa64.txt").unwrap();
let mut name_a = String::new();
f.read_to_string(&mut name_a).unwrap();
let lib = libloading::Library::new(&name_a);
```

```
**【修复建议】**

使用白名单机制，确保加载函数的参数不受任何外来数据的影响。
