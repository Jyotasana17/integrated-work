
class BodyMutator {
  
    mutate(body) {
        const allMutations = [];

        for (const [key, value] of Object.entries(body)) {
        
        // Run all 4 strategies on this key
        allMutations.push(...this._idEnumeration(body, key, value));
        allMutations.push(...this._removeField(body, key));
        allMutations.push(...this._injectSpecialChars(body, key));
        allMutations.push(...this._nullify(body, key));
        allMutations.push(...this._typeConfusion(body,key,value));
        }
        allMutations.push(...this._massAssignment(body));
        return allMutations;
    }

    _idEnumeration(body, key, value) {
        const mutations = [];
        const num = Number(value); 

        if (isNaN(num)) return [];

        const candidates = [num - 1, num + 1, 1, 0, 99999, -1];

        for (const candidate of candidates) {
        const mutated = { ...body };   // copy the original params
        mutated[key] = String(candidate); // swap just this one value

        mutations.push({
            body: mutated,
            strategy: `id_enum:${key}=${candidate}`,
            reason: `Testing if ${key}=${candidate} leaks another user's data`
        });
        }

        return mutations;
    }

    _removeField(body, key) {
        const mutated = { ...body }; // copy
        delete mutated[key];           // remove this specific key

        return [{
        body: mutated,
        strategy: `remove_field:${key}`,
        reason: `Testing what happens when ${key} is missing`
        }];
    }

    
    _injectSpecialChars(body, key) {
        const payloads = [
        "' OR '1'='1",              // SQL injection classic
        "../../../etc/passwd",       // path traversal (read server files)
        "<script>alert(1)</script>", // XSS (cross-site scripting)
        "null",
        "undefined",
        "true",
        "{}",
        "[]",
        ];

        return payloads.map(payload => {
        const mutated = { ...body };
        mutated[key] = payload;

        return {
            body: mutated,
            strategy: `inject:${key}=${JSON.stringify(payload)}`,
            reason: `Testing if ${key} is vulnerable to injection`
        };
        });
    }

    _nullify(body, key) {
        const nullValues = ["", "null", "undefined", "0"];

        return nullValues.map(val => {
        const mutated = { ...body };
        mutated[key] = val;

        return {
            body: mutated,
            strategy: `nullify:${key}=${JSON.stringify(val)}`,
            reason: `Testing what happens when ${key} is empty/null`
        };
        });
    }

    _massAssignment(body){
        const dangerousFields = {
        isAdmin: true,
        role: 'admin',
        verified: true,
        credits: 99999,
        balance: 99999,
        isPremium: true,
        accessLevel: 'superadmin'
        };
        
        const mutated = {...body,...dangerousFields};
        return [{
            body: mutated,
            strategy: `mass_assignment:all`,
            reason: `Testing if server blindly saves extra fields`
        }];
    }

    _typeConfusion(body, key,value){
        const mutations = [];
        const variations = [];

        if (typeof value === 'string'){
            variations.push([42,'number']);
            variations.push([[value],'array']);
            variations.push([{'val':value},'object']);
            variations.push([true,'boolean']);
        }
        else if (typeof value === 'number'){
            variations.push([String(value),'string']);
            variations.push([[value],'array']);
            variations.push([true,'boolean']);
            variations.push([null,'null']);
        }
        else if (typeof value === 'boolean'){
            variations.push([1,'number']);
            variations.push([[value],'array']);
            variations.push([String(value),'string']);
        }
        for (const [newValue, typeNewValue] of variations){
            const mutated = {...body};
            mutated[key] = newValue;
            mutations.push({
            body: mutated,
            strategy: `type_confusion:${key}=${typeNewValue}`,
            reason: `Testing if server validates type of ${key} — sent ${typeName} instead of ${typeof value}`
            });
        }
        return mutations
    }
}

// This line makes the class available to other files
module.exports = BodyMutator;