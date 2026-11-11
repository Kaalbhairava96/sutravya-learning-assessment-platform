'use strict';
const assert = require('node:assert/strict');
global.window = {};
require('../question-bank.js');
const banks = window.HTSE_QUESTION_BANK;
const pathwayKeys = ['paramedical', 'nursing', 'mbbs_ug', 'mbbs_pg'];
const expected = {
 paramedical: ['anatomy_physiology','laboratory_sciences','microbiology_infection_control','diagnostic_technology','patient_safety_communication'],
 nursing: ['nursing_foundations','applied_anatomy_physiology','nutrition_biochemistry','psychology_community','infection_safety_ethics'],
 mbbs_ug: ['anatomy','physiology','biochemistry','foundation_aetcom','community_research'],
 mbbs_pg: ['medicine','surgery','obgyn_paediatrics','pathology_pharmacology','microbiology_forensic_allied']
};
for (const key of pathwayKeys) {
 const bank = banks[key];
 assert.ok(bank, 'Missing practice bank: ' + key);
 assert.equal(bank.questions.length, 100, key + ': 100-question count');
 assert.deepEqual(bank.subjects.map(x => x.key), expected[key], key + ': syllabus subject list');
 const ids = new Set();
 const counts = Object.fromEntries(expected[key].map(x => [x, 0]));
 const positions = [0, 0, 0, 0];
 for (const [index, q] of bank.questions.entries()) {
   assert.ok(q.id && !ids.has(q.id), key + ': missing or duplicate ID at question ' + (index + 1));
   ids.add(q.id);
   assert.ok(typeof q.question === 'string' && q.question.trim(), key + ': missing question text');
   assert.equal(q.options.length, 4, key + ': option count at question ' + (index + 1));
   assert.ok(q.options.every(x => typeof x === 'string' && x.trim()), key + ': empty option');
   assert.ok(Number.isInteger(q.answer) && q.answer >= 0 && q.answer < 4, key + ': invalid answer position');
   assert.ok(typeof q.explanation === 'string' && q.explanation.trim(), key + ': missing explanation');
   assert.ok(Object.hasOwn(counts, q.subjectKey), key + ': unmapped subject ' + q.subjectKey);
   assert.equal(q.subjectLabel, bank.subjects.find(x => x.key === q.subjectKey).label, key + ': subject label mismatch');
   counts[q.subjectKey]++;
   positions[q.answer]++;
 }
 for (const subject of bank.subjects) assert.equal(counts[subject.key], subject.question_count, key + ': declared subject count mismatch');
 assert.equal(Object.values(counts).reduce((a,b)=>a+b,0), 100, key + ': subject counts total');
 assert.ok(positions.every(x=>x>0), key + ': answer key never uses one or more options');
 if (key === 'mbbs_pg') assert.deepEqual(positions,[25,25,25,25], 'MBBS PG answer key positions should be evenly distributed');
 console.log(key + ': 100 valid questions; subject counts ' + Object.values(counts).join('/') + '; answer positions ' + positions.join('/'));
}
